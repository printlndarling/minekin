# P0 required-case 证据盘点（P0-EVIDENCE-INVENTORY-001）

> 只读盘点记录，2026-09-26，baseline `37f8deb56fb38836f17845fe2b3f51b9ef39af96`（in-image python 3.12.3）。
> 目的（执行计划 B1 卡面）：把**契约要求的 74 条 case** 在**规范数据卷**与**当前仓库构建**上逐条标注到四个桶里——
> 缺 fixture、缺当前 build 真证据、真实失败、产品未实现——并说明每条门的阻塞来自哪一类。
> 本记录**不改**产品代码、case 判据、registry 字节、`status/gaps` 或任何已封存证据；失败材料一律保留。
> **盘点本身不是门绿**：§3 逐门读数今天全是 `promotable: false`（除 W00/W10/W20 三条本就为 true），
> 这张卡一张门都不点亮。
> 挂载即证据：两次 run 都用 `-v …:/src:ro -v …:/data:ro`；读数日志开头印 `src readable True | data writable False`，反证日志开头印 `src writable False | data writable False`（都是 `os.access(..., os.W_OK)`）。全程未连接任何远程服务器。

## 0. 复现入口

两个脚本都是 `.tmp/` 未跟踪文件，同一镜像、同一只读挂载：

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
# 读数（§0–§9 共 14 个小节）
docker run --rm --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -w /src minekin-runner:local -lc 'bash /src/.tmp/b1-evidence-inventory.sh'
# 反证（证明这个视图能判红）
docker run --rm --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -w /src minekin-runner:local -lc 'bash /src/.tmp/b1-inventory-reversals.sh'
```

§5 的六个代码锚点不必进容器，仓库里直接复核：

```bash
grep -n "OFFLINE_SESSION_CANDIDATES\|user_type_argv\|def candidate_by_id" -A 2 \
  src/minekin_core/adapters/launcher/offline_session.py          # :87 / :50,:59 / :90
grep -rn "identity_revision" src --include=*.py                  # 只有读与 init 写，无 UPDATE/自增
grep -n "classifyDisconnect" -A 24 \
  bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java   # :426
grep -n "CLIENT_STREAM_ARTIFACTS\|previous-run-trace" tools/assert_case_evidence.py  # :709 / :693
grep -n "credential" src/minekin_core/adapters/evidence/bundle.py                    # :5,:8,:128,:136
grep -n "server_profile_id\|message ConnectionLifecycle" proto/minekin/v1/observation.proto  # :74 / :72
```

日志：`.tmp/b1-evidence-inventory.log`（§0–§9，其中 §2b/§3b/§6b/§7b/§9 是这张卡补的五段）、`.tmp/b1-inventory-reversals.log`（P/R1–R4）。
本文每个数字出自这两份日志或 `tests/fixtures/cases/*.json` 本身；§5 的代码锚点另给一条 grep 入口（见下）。
下文**「日志 §N」指读数日志的小节**，不带前缀的 §N 指本文小节。

盘点视图（`.tmp/b1-inventory-join.py`）**不产生新判定**：它把两个既有机器读者接起来——

| 输入 | 出自 | 提供什么 |
| --- | --- | --- |
| `report_cases.py` | 冻结的 required-case inventory（`src/minekin_core/domain/cases.py` 的 `REQUIRED_CASES`） | 74 条要求、判定者、`local-only`/`runtime-required`、契约锚点、fixture 在不在 |
| `report_promotion.py --data-root /data` | 规范卷上 86 个 bundle | 每条 case 有哪些 attempt、结果、是否当前 build、是否 verified、re-judge 结论、逐门 blocks |
| case 摘要转储（日志 §2b） | `load_case_registry(tests/fixtures/cases)`，与晋级规则加载的是同一个 registry | 让「判据移动了」这一格由 `case_version == case.digest` 回答，而不是由 `re_judged` 猜 |

第三份输入是这张卡第一次跑时补上的：`re_judged: UNJUDGED` 同时涵盖「判官没被问」与「这份 bundle 对自己的字节沉默」两种情况，
拿它当「判据变了」的证据会把三条**其实匹配今天摘要**的行（CORE-001、CORE-070、W00-CONTRACT-001）误分进错误桶。
误分的后果不是小数：那会把 W10/W60/W00 三门写成「缺证据」，而工具读数是 W00/W10 可晋级、W60 只被
`CASE_VERSION_MISMATCH` 阻塞。日志 §8 的最后一条对账就是这个坑的护栏。

## 1. 一句话读数

74 条被契约要求的 case：**31 条没有 fixture**、**28 条有 fixture 但规范卷上没有当前构建的可用证据**、
**15 条有当前构建的可用通过证据**、**0 条在 required 集合内是当前构建上的真实失败**。
7 条 mandatory 里只有 **CORE-040、CORE-050** 两条拿不到当前构建证据，二者共同造成 W60 与 `p0-core` 的 `CASE_VERSION_MISMATCH`。

| 桶 | 条数 | 含义（工具词汇） |
| --- | --- | --- |
| `missing_fixture` | 31 | 契约要求、`tests/fixtures/cases/` 下没有 case 定义 ⇒ `REQUIRED_CASE_NOT_REGISTERED` |
| `no_current_build_evidence` | 28 | 有定义，但最新 attempt 里没有「当前 build + verified + 摘要匹配 + 判官未反对」的通过行 |
| `real_failure_on_current_build` | 0 | 有当前 build 的可用证据，且它判 `FAIL` 或被判官反对 |
| `current_build_pass` | 15 | 有当前构建上可用且通过的一行 |

`no_current_build_evidence` 的两种成因（§6 逐条）：**18 条 `no_bundle_on_this_root`**（这根上从没有过它的 bundle）、
**10 条 `only_another_build`**（有 bundle，但都不是当前构建封的）。
第三种成因 `current_build_sealed_against_older_criteria`（当前 build 但摘要对不上）今天在规范卷上**为空**——
它能被触发（§8 R4 用一位十六进制的改动就触发了），只是这台机器上恰好没有这种行。

还有一格必须连同桶数一起读：那 15 条「当前构建上有可用通过证据」的行，**全部来自同一个构建身份**
（日志 §3b 逐条打印 `mc / plan / bridge`，去重结果是单元素 `[["1.21.4", "bcc0c10d", "0ee2070b"]]`）。
也就是说，required 集合今天的当前构建证据**全在 1.21.4 那一侧**；1.20.1 的产品主线证据属于 `V1201-*` 族，
而该族不在这 74 条里（§4）。这不改变任何门的读数（`from_repository_build` 对两个版本分别比对各自的 reviewed plan），
但它决定了「补一轮当前构建真跑」这句话在 1.20.1 主线上是什么量级的事。

## 2. 74 条的四桶名单（机器输出，非人工归置）

- **`current_build_pass` 15 条**：`W00-CONTRACT-001`、`CORE-001`、`CORE-010`、`CORE-020`、`CORE-070`（7 条 mandatory 中的 5 条）、
  `CORE-060`、`CORE-060-CLIENT-001`、`CORE-060-SERVER-001`、`CORE-090`、`CORE-100`、`ADMIT-070`、
  `OFFLINE-010`、`OFFLINE-020`、`OFFLINE-030-ENUM-ALIGNED-001`、`OFFLINE-030-PRISM-PARITY-001`。
- **`no_current_build_evidence` 28 条**：
  `no_bundle_on_this_root` 18 = `OFFLINE-001/030/040/050`、`ADMIT-080`、`HOST-010/020/050/060/070/080`、
  `HOSTCOMMIT-090/110`、`HOSTCTL-001/010/050/060/070`；
  `only_another_build` 10 = `ADMIT-001/040/060/100/110`、`CORE-030/040/050`、`HOST-030/040`。
- **`missing_fixture` 31 条**：见 §5 逐族表。

`report_cases.py` 的登记侧读数（与桶数交叉核对，日志 §8 第 1 条）：`required 74 / present 43 / missing 31 /
not_gating 36 / misattributed 0`，注册 case 49 个、mandatory 7 个、断言引用 184 条，
`by_judge` 为 `locally 20 / run-material 29 / mixed 0 / unimplemented 0`，`unregistered_assertions 0`。

## 3. 逐门读数：门为什么没绿，和「case 有没有证据」是两件事

`report_promotion.py --data-root /data`（`rc=1` 读作「不晋级」，不读作「坏了」）：

| 门 | promotable | blocks | 阻塞来自哪一条 |
| --- | --- | --- | --- |
| W00 | true | — | 唯一要求的 `W00-CONTRACT-001` 在当前 build 上有可用通过证据 |
| W10 | true | — | 同上（`CORE-001`，仓库自检类，判官 `locally`） |
| W20 | true | — | 同上（`CORE-010`，attempt 3 `3c1d0350…`） |
| W30 | false | `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED` | 8 条 present 全 `mandatory: false`；另缺 `OFFLINE-060…100` 五条定义 |
| W40 | false | `REQUIRED_CASE_NOT_REGISTERED` | `CORE-020` 本身有当前 build 证据（attempt 2 `d3b3a4d5…`）；缺的是 ADMIT 五条定义 |
| W50 | false | `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED` | present 仅 1 条且非 mandatory；缺 `ADMIT-120`、`CORE-080` 定义 |
| W60 | false | `CASE_VERSION_MISMATCH` | `CORE-040`（4 个 bundle 全在别的 build 上）、`CORE-050`（3 个同样） |
| W70 | false | `NO_MANDATORY_CASES` | 5 条 present 全非 mandatory，**没有一条缺定义** |
| host-integrated | false | `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED` | 15 条 present 全非 mandatory；`requirement.absent` 在这门上就是 18 条 HOST/HOSTCTL/HOSTCOMMIT |
| p0-core | false | `CASE_VERSION_MISMATCH` + `REQUIRED_CASE_NOT_REGISTERED` | 两类同时命中：`CORE-040/050` 摘要不匹配 + 12 条缺定义 |
| p0-nav-exp | false | `NO_MANDATORY_CASES` + `REQUIRED_CASE_NOT_REGISTERED` | 这一门只要求 `NAV-EXP-010`，而它没有定义 |

三种 block 的语义差别就是这张表的存在理由：

- `REQUIRED_CASE_NOT_REGISTERED` = 定义都没有，**写代码之前先要判据设计**；
- `CASE_VERSION_MISMATCH` = 定义有、证据有，但那份封证判的不是今天的判据，**要一轮当前构建真跑**；
- `NO_MANDATORY_CASES` = 定义与判据都在、且都还没被点亮为门禁，**是主控的门禁决策**，不是谁的实现缺口。

顺带纠正一处契约文档滞后（**不改写原文，登记读数**）：
`docs/p0-validation-evidence-contract.md` 的 crash/outbox 表把 runtime 强杀那一窗写成「有 2 份 attempt、都判 `FAIL`、
剩下那条按当前 run 形状打不中」。规范卷今天对该 case id 有 9 个 bundle（日志 §7b 逐条），其中带 `attempt_sequence` 的链条是
seq1 `08f206bf…` FAIL → seq2 `412b874b…` FAIL → seq3 `7fc0671e…` PASS → **seq4 `ed2bbad7…` PASS 且 `from_repository_build: true`**。
按晋级规则「有 `attempt_sequence` 时只取最高那一档」，`CORE-060` 今天读作「当前构建上有可用通过证据」；
它仍是 `mandatory: false`，所以这不让任何门变绿，但那一格「打不中」的说法已经落后于磁盘。
**滞后的来源不是失踪的 run**：那两条等强 PASS 是 1.21.4 换代重封运动的产物，历史
[`:5936-5941`](development-execution-history-through-cef712b.md#L5936) 的 `reseal_runs_identity` 十二案清单里就有
`CORE-060 7fc0671e…→ed2bbad7051f…`(att 4, bundle `1b3449cd…`)。也就是说磁盘与历史都记了，只有契约那张表没跟着改。

## 4. 「真实失败」这一桶：在 required 集合内为空，但卷上有失败材料

- `report_promotion` 卷内 86 个 bundle 里有 **14 份 sealed `FAIL`**，其中 **2 份在当前构建上**：`V1201-080` seq1 `6d11ab7d…`、seq2 `ffdd54fc…`（两份都 `verified: true`、`re_judged: AGREES`，即判官同意它们该红）。
- **但 `V1201-*` 族不在这 74 条 required 名单里**（它是 1.20.1 bundle 条目的本地复演家族），
  所以「`real_failure_on_current_build` = 0」这句的完整说法是：
  **被契约要求的 74 条里，没有一条在当前构建上留着可用的失败封证**——不是「这卷上没有失败」。
- 全卷 86 份 bundle 里**只有一份**判官反对自身字节：`ADMIT-060` seq1 `3c17aa78…`
  （`re_judged: DISAGREES`，原因原样 `RESULT:recorded=FAIL,re-judged=PASS`，在别的 build 上）——
  它记的是失败，而今天的判据读同一份字节判出通过。这一份是「反对」而不是「沉默」，按 `cases.py` 的规则它才阻塞，
  `UNJUDGED` 不阻塞。它已被同 case 的 seq2 `7bc740ea…`（PASS/AGREES，仍非当前 build）取代。
- 14 份 FAIL 与其余 61 份 `from_another_build` 全部原样保留，本卡不删、不撤、不改写。

## 5. 31 条缺 fixture：按族 + 每条缺的是「断言」还是「产品事实」

分类口径沿用本仓库自己为 ADMIT 族立下的两分（`docs/development-execution-history-through-cef712b.md:6292-6303`）：
**（甲）事实已经记了、只是没人断言** ⇒ 测试域写断言即可；
**（乙）该事实根本没有产品载体** ⇒ 那是产品改动，不是写测试。

**先记一处需要更正的旧口径**：同文 `:3385-3391` 把这 31 条的阻断原因统一写成
「`ADMIT-010/020/030/050/090/120`、`OFFLINE-060/070/080/090/100`、`CORE-080` 需先把判据写成断言」。
OFFLINE 那五条按今天的代码逐条查下来，**有三条不能只靠写断言闭合**（见下表），那句统一归类对它们不成立。
原文照引不改，本节是其后的复核。

| 族 / case | 契约锚点 | 缺什么（甲/乙） | 依据 |
| --- | --- | --- | --- |
| `ADMIT-010`、`ADMIT-020` | `p0-remote-admission-contract.md` | **乙**：线缆上 `ConnectionLifecycle` 带 `server_profile_id`/`server_profile_revision`（`proto/minekin/v1/observation.proto`），但 Core 写账本那一行只剩 `phase`/`reason`，profile 与 SRV 结果被丢掉 | 历史 `:6324-6325`，本卡不重判 |
| `ADMIT-030`、`ADMIT-050` | 同上 | **甲，但先要契约层面的拆分决定**：两条各自把三个互斥场景塞进一个 case id，而 promotion 对一个 case id 是 any-satisfying-bundle | 历史 `:6326`、`:6328` 与 `:6292-6303` 的两分口径 |
| `ADMIT-090` | 同上 | **乙**：「人格没有被重建」在账本现有事件类型里无承载 | 历史 `:6330` |
| `ADMIT-120` | `p0-validation-evidence-contract.md:194` | **乙**：oracle canary 的 containment 在运行材料里没有来源 | 历史 `:6331` |
| `CORE-080` | 同契约 `:191` | **乙/整条缺失**：故意向 oracle 放置 Kin 未看见的事实后，检查所有 Runtime/Memory/模型输入均不存在该事实——运行期那半今天无断言亦无材料 | 契约第 9 项原文 |
| `OFFLINE-060` | `p0-offline-session-compatibility-contract.md:152` | **乙**：候选集在代码里封闭为两个（`adapters/launcher/offline_session.py:67-87`，`__post_init__:59-60` 禁空 `user_type_argv`；`candidate_by_id:90` 对未知 id 直接拒绝、不回退）。契约要的 OFF-D（删整对参数）/OFF-N（无效 userType 串）**根本无法启动**，因此也没有承载其结果的事件或工件 | 本卡复核 |
| `OFFLINE-070` | 同契约 `:153` | **混合**：「同名冲突分类」有载体（`ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN`，`bridge/.../ClientAdmissionController.java:435`）→ 甲；「新 revision」与「人格根不合并」**无载体**——`identity_revision` 只在 `cli/init.py:77` 写成常量 1，全仓库无自增/更新路径（schema 只约束 `>= 1`）→ 乙 | 本卡复核 |
| `OFFLINE-080` | 同契约 `:154` | **混合**：白名单与 `AUTH_MODE_MISMATCH` 两类已在账本 `SessionInterrupted.reason` 里、且有现成断言可复用（`tools/assert_case_evidence.py`）→ 甲；**封禁**无载体：Bridge 的 `classifyDisconnect`（`bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:426-447`）逐条匹配 vanilla 那句白名单/重名/认证/版本/资源包文案，**没有任何 banned 分支**，一句封禁响应会按设计落到 `UNEXPECTED_DISCONNECT`，而 `AdmissionFailureReason` 的 16 个具名分类（另加 `UNSPECIFIED`）里也没有 ban 类；仓库内 `banned` 只出现在 `bridge*/host-boundary-names.json` 的 vanilla 类名清单里 → 乙 | 本卡复核 |
| `OFFLINE-090` | 同契约 `:155` | **甲，限定在 bundle 范围内**：待计数的字节都已封存——`client/stdout.log`、`client/stderr.log`、`client/latest.log`（`tools/assert_case_evidence.py:709` 的 `CLIENT_STREAM_ARTIFACTS`，`tools/seal_run_evidence.py:250` 逐个封）、`client/crash-reports/*`（`:252-254`）、`server/server.log`（`:256`）与账本全时间线；而 `adapters/evidence/bundle.py:5-9` 对 credential 字面量是**拒封而非脱敏**（redacting in place would seal a silently altered log）——那是门禁不是证据，所以「正文暴露次数为 0」可以对既有字节写成断言。**但 Dashboard 不在任何封存工件里**，契约这半句今天判官材料覆盖不到，须登记为材料外边界 | 本卡复核 |
| `OFFLINE-100` | 同契约 `:156` | **甲**：`kin_id`、`world_context_id` 都是账本导出列，上一条 run 的时间线已封为 `previous-run-trace.jsonl`（名字在 `tools/assert_case_evidence.py:693`，写入在 `tools/seal_run_evidence.py:799-800`，仅当 `material.previous_run_id` 非空），重启侧断言已存在（为 `CORE-090` 写的，共用允许）。**限定**：A→B→A 跨多个 run，而单 bundle 只带一份 previous 时间线，跨 run 链是 EVIDENCE-SEQUENCE 形状，不是一份 bundle | 本卡复核 |
| `HOST-001/090/100`、`HOSTCTL-020/030/040/080/090`、`HOSTCOMMIT-001…080,100`（共 18 条） | 三份 hosted-world 契约 | **不判**：`host-integrated` 整族在 hosted-world 契约 §5 的三个 ownership 单元格由主控冻结之前属 `DEFERRED`。把它记成「产品未实现」是替主控做决策 | 计划与交接的边界注记 |
| `NAV-EXP-010` | `p0-validation-evidence-contract.md:195` 第 13 项 | **依赖门**：契约写明「只在 core tested 后运行」，而 `p0-core` 今天不可晋级（§3） | 契约原文 |

**因此「产品未实现」这一桶的正确读法是**：在**已注册**的 case 上它是空的（`by_judge.unimplemented == 0`、
`mixed == 0`，184 条断言引用全部登记了判官）；在**缺 fixture** 的 31 条上，它由「该事实有没有产品载体」决定，
今天点名到 **6 条整条**（`ADMIT-010`、`ADMIT-020`、`ADMIT-090`、`ADMIT-120`、`CORE-080`、`OFFLINE-060`）
与 **2 个半句**（`OFFLINE-070` 的 revision/人格根那半、`OFFLINE-080` 的封禁那半）。

**这次复核同时改写了旧清单里的一句**：历史 `:6328` 说 `ADMIT-050` 缺「封禁与重名两类各自的分类」。
今天的代码里**重名那一半有载体**（`classifyDisconnect` 把 `already connected` / `logged in from another location`
映射为 `ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN`，`ClientAdmissionController.java:433-435`，另有 Java 侧单测），
**封禁那一半确实没有**——所缺的否定判据（不误判成版本/认证）也仍缺。原句照引不改，本段为其后的复核。

## 6. 28 条有 fixture 无当前构建证据：逐条读的是哪个原因

`no_bundle_on_this_root` 18 条里，`OFFLINE-001/030/040/050`、`ADMIT-080` 属 W30/W40 的**非 mandatory** 行，
`HOST-*`/`HOSTCTL-*`/`HOSTCOMMIT-*` 14 条属 deferred 族（有 fixture、但契约族本身等主控决策，见 §5 末两行）。

`only_another_build` 10 条：`ADMIT-001/040/060/100/110`、`CORE-030`、`CORE-040`、`CORE-050`、`HOST-030`、`HOST-040`。
其中只有 `CORE-040`、`CORE-050` 是 mandatory，也正是 §3 里 W60/`p0-core` 的 `CASE_VERSION_MISMATCH` 来源（下面两组摘要逐份取自日志 §6b，那里把每份 bundle 封进去的 `case_version` 与今天 registry 的摘要并排印出，`match=False`）：

- `CORE-040` 4 份 bundle（`06577911…` PASS、`ad37887d…` FAIL、`c67bef3e…` FAIL、`e08163aa…` PASS）全部 `from_repository_build: false`，
  封进去的 `case_version` 只有两个值（`043066a0ff24…`、`63fb31a5a96d…`），都对不上今天的 `22906123eeb7…`；
- `CORE-050` 3 份 bundle（`52cb5647…`、`85fe770f…`、`fe0973f9…` 全 PASS）同样在别的 build 上，
  `case_version` 为 `2e7cba625d59…` 或 `3400b51d7cb4…`，对不上今天的 `4b88854a5d46…`。

这两条要的是**一轮当前构建上的真实运行**（move/look/use 与首快照前拒输入），不是新判据。

## 7. 登记为缺口、但不算做完的四格

这张卡是只读拼接，所以它量出的**运行级**缺口一律另卡闭合，本卡不点亮任何东西：

- **缺 fixture / 缺断言设计**：§5 的 31 条。写一条 case 定义即定义一次 PASS，属逐案判据设计，B1 不自造断言。
- **缺当前 build 的 mandatory 真跑**：§6 点名的 `CORE-040`、`CORE-050`。日志 §9 把那 28 行按判据形状切成三格，
  三格恰分整个桶（`1 + 10 + 17 = 28`）：**判官要运行材料且本根零 bundle 1 条**（`OFFLINE-030`）、
  **判官要运行材料但只有别的构建上的 bundle 10 条**（`ADMIT-001/040/060/100/110`、`CORE-030/040/050`、`HOST-030/040`，
  其中 mandatory 只有 `CORE-040`、`CORE-050` 两条）、**判官只需仓库字节但本根零 bundle 17 条**。
  前两种形状合起来（11 条，去掉 deferred 的 `HOST-030/040` 是 9 条）就是 `P0-CONTROLLED-CAMPAIGN-001` 的最小内容。
- **缺 1.20.1 主线侧的当前构建证据**：§1 末段那格（15 条当前构建通过行全在 1.21.4 身份上）。
  它不改变任何门读数，但「补一轮当前构建真跑」在主线上的量级由它决定。
- **缺决策而不是缺代码**：§5 的 6 条整条 + 2 个半句（乙类）、`ADMIT-030/050` 的 case id 拆分、HOST 18 条的三个 ownership 单元格。

明确不做的事：不点亮任何门、不改 `mandatory` 标志、不换 registry 引用摘要、不重跑真实 Minecraft 运行
（本卡一次真实运行都没有，受控域/V08/远程服均未触碰）、不给缺 fixture 的 31 条写断言或 case 定义、
不判 deferred 的 HOST 族「是不是产品未实现」。`V1201-080` 的两份 sealed FAIL 与 61 份其他构建的 bundle 保留原状，
本卡不据它们宣布任何完成，也不清理它们。

## 8. 反证：这个视图能不能判红

正对照就是 §1/§2 的 15/31/28/0；四个破坏各移一个不同机制，全部在 `/tmp` 里做，`/src` 与 `/data` 只读
（反证日志 §0 印 `src writable False | data writable False`；读数日志 §0 印 `data writable False`）：

| 反转 | 做法 | 读数 |
| --- | --- | --- |
| R1 | `/tmp` 里复制 case 目录、删掉 `core-001.json`，用 `report_cases.py --cases-dir` 重读 | `required_missing 31 → 32`，`CORE-001` 落 `missing_fixture`，`current_build_pass 15 → 14`。它对日志 §8 的对账护栏**不触发**——那是设计如此：该护栏只覆盖 fixture 在册的行，删定义的证据变化由 `report_cases` 自己判红 |
| R2 | 指向一个空数据根（`report_promotion --data-root /tmp/…/empty-root`，`evidence.count = 0`） | `current_build_pass` 整桶消失（15 → 0），28 条 `no_current_build_evidence` → 43，原因全为 `no_bundle_on_this_root`，`missing_fixture` 仍 31 ⇒ 桶只随磁盘证据移动 |
| R3 | 复制 promotion 文档，把 `CORE-070` 在当前 build 上的那行 `PASS` 改成 `FAIL` | `real_failure_on_current_build` 出现 `['CORE-070']`、`mandatory_without_current_pass` 变成 `['CORE-040','CORE-050','CORE-070']`，并且日志 §8 的护栏同时报 `['CORE-070']`——因为 `work_packages` 是工具写的、没跟着重算，视图与规则一旦不一致就被跑出来，不会被静悄悄带走 |
| R4 | 把 case 摘要转储里 `CORE-010` 的 digest 改一位十六进制 | `CORE-010` 从 `usable_current_build_evidence` 变 `current_build_sealed_against_older_criteria`，第三种成因第一次被真实触发；护栏同时报 `['CORE-010']` |

日志 §8 的八条自检在真件上全 `PASS`、`consistency FAIL count = 0`；反证段七条全 `PASS`、`reversal FAIL count = 0`。

## 9. 排卡建议：只有两组够得上「有明确必要性」

B1 的卡面判据是「只把**有明确必要性**的 missing case 排成独立实现卡」。按这句筛，31 条缺 fixture 里
今天够得上「排一张卡」的只有两组，其余三类**要么前置是主控决策、要么属 deferred 族**，
给它们编卡号就是替主控做产品决定——本节只登记所需选择与证据形状，不占队列。
登记落点在[执行计划 §3.3](development-execution-plan.md)。

### 9.1 建议新卡 1：`P0-CORE-040-050-RUN-001`（状态 `QUEUED`，本地 + 真跑）

- **为什么必要**：7 条 mandatory 里唯二只差运行的行（§6）。W60 与 `p0-core` 今天的唯一 block 就是这两条的
  `CASE_VERSION_MISMATCH`，判据现成、无需新断言。
- **完成判据（逐字取自磁盘）**：`CORE-040` 今天的 case 摘要 `22906123eeb7…`、`CORE-050` 是 `4b88854a5d46…`（日志 §6b 头两行）；
  两条各在**当前仓库构建**上留一份 `verified`、`case_version == 今天的 digest`、`result == PASS`、
  且 `from_repository_build: true` 的 bundle；`report_promotion --data-root /data` 对 W60 不再报 `CASE_VERSION_MISMATCH`。
- **非空转反证**：沿用 §8 R4 的形状——把读到的 `case_version` 改一位 ⇒ 该行落 `current_build_sealed_against_older_criteria`，
  门重新判红。旧 attempt 一律保留，不做「替换式清理」。
- **不做什么**：不点亮任何门、不改 `mandatory`；跑绿之后 `report_promotion` 的 `promotable` 只是候选，
  晋级仍是主控动作（`P0-GATE-PROMOTION-001`）。

### 9.2 建议新卡 2：`P0-OFFLINE-090-100-EVIDENCE-CHECK-001`（状态 `QUEUED`，先本地判据、后真跑）

- **为什么必要**：§5 判为**甲**（事实已封、只是没人断言）的两条。待计数的字节已在 bundle 里——
  `client/stdout.log`、`client/stderr.log`、`client/latest.log`（`tools/assert_case_evidence.py:709` 的
  `CLIENT_STREAM_ARTIFACTS`，`tools/seal_run_evidence.py:250` 逐个封）、`client/crash-reports/*`（`:252-254`）、
  `server/server.log`（`:256`）与账本全时间线；重启侧断言已为 `CORE-090` 写好可共用。
- **完成判据**：两条各有一份 case 定义 + 断言，且在当前构建的 bundle 上判 `PASS`；
  `OFFLINE-100` 的 A→B→A 跨 run 链按 `EVIDENCE-SEQUENCE` 形状做（单 bundle 只带一份 previous 时间线，见 §5）。
- **必须同时登记的边界**：`OFFLINE-090` 的「Dashboard 不暴露凭据」那半句**不在任何封存工件里**，
  只能登记为材料外边界，不许用 bundle 内的「正文暴露次数为 0」冒充整条闭合；
  而 `adapters/evidence/bundle.py:5-9` 对 credential 字面量是**拒封而非脱敏**——那是门禁不是证据，
  「一次正文暴露」的真实运行今天封不出 bundle，这一条要在卡面先讲清。
- **非空转反证**：向日志副本注入一次凭据字面量 ⇒ 断言判红（同时验证拒封路径确实被绕过了副本而不是被测物）。

### 9.3 三类今天不编卡号，只登记所需选择

| 类别 | 条数 | 今天缺的是哪一个选择（不是缺代码） |
| --- | --- | --- |
| 产品事实无载体 | 6 条整条（`ADMIT-010`、`ADMIT-020`、`ADMIT-090`、`ADMIT-120`、`CORE-080`、`OFFLINE-060`）+ 2 个半句（`OFFLINE-070` 的 revision／人格根那半，`OFFLINE-080` 的封禁那半） | 账本那一行是否承载 profile/endpoint；身份是否承载「未重建」；canary/oracle containment 的运行期来源；OFF-D/OFF-N 是否进入 reviewed 候选集；`identity_revision` 是否有变更事件；封禁是否成为独立准入分类 |
| case id 拆分 | 2 条（`ADMIT-030`、`ADMIT-050`） | 一个 case id 装三个互斥场景，而 promotion 对同一 id 取任一满足 bundle，正向证据会顺带关掉互斥的负向判据；拆分属契约层决定 |
| deferred 族 | 18 条（HOST / HOSTCTL / HOSTCOMMIT）+ 1 条依赖门（`NAV-EXP-010`） | 前者等主控对 hosted-world 契约 §5 三个 ownership 单元格表态；后者契约原文写明「只在 core tested 后运行」，而 `p0-core` 今天不可晋级（§3） |

另有两处**本卡顺手量到、但不在上面三组里**的交叉事实：`report_promotion` 侧的 `requirement.absent` 是 31 条、
`requirement.non_mandatory` 是 36 条（日志 §2 的 `overall` 行，两个名单也逐条印在同一行里），
与 `report_cases` 侧的 `required_missing 31`、`required_not_gating 36` **数上相等**——即「缺定义」与
「契约要求但不进门禁」在两台上是同一批行，§5 与 §3 说的不是两套账。日志 §8 的第 1 条把
`missing_fixture == required_missing`、第 5 条把 `required_not_gating == joiner 里 present 且非 mandatory` 写成自检；
promotion 那两个名单是同数的第三个读者，本卡按名对读，不另加机器断言。
至于「每条 required 恰落一桶」，那是日志 §8 第 2 条守住的
（`sum(by_bucket_count) == required_cases == len(report_cases requirements)`），所以 §2 的名单不会重也不会漏。
