# tested 晋级门复判记录（VERSION-TESTED-GATE-AUDIT-001）

> 只读审查记录，2026-09-25。范围：`tests/fixtures/registry/reviewed-tested-bundles.json` 里 1.20.1 条目的
> `status: tested` 在**原始 V04/V05/V06 契约**下能否独立复判。本记录**不改**产品代码、registry 字节、case 判据
> 或任何封存证据；它只做三件事：给出追溯表、判定当前 `tested` 在两条用途上各自能不能用、把确证的缺口登记成
> 有范围与门禁的后续卡。所有引用都是 `file:line`，可复核。

## 1. 追溯表：原始要求 → 本 build 的实际证据 → 结论

| # | 原始要求（出处） | 实际证据（可复判） | 结论 |
| --- | --- | --- | --- |
| A1 | 1.20.1 客户端能在受控 1.20.1 真服上入服、有界移动、松键并正常停止（V04 卡 `question`，主计划 :3394） | V04 四个 run 与服务端读数；`tests/fixtures/cases/v1201-040.json:3-23` 断言 `move_input_was_leased`、`the_server_saw_the_kin_move`、`the_lease_expired_and_was_released` 等 | **成立（限 lease 到期路径）**：入服、移动、转向、lease 到期松键都有服务端独立读数 |
| A2 | **断连/停止阶段的显式松键送达**（`docs/version-auto-to-server-control-plan.md:211` "断连松键及正常停止"；`docs/p0-core-internal-architecture.md:304` watchdog 保障） | 同一 run 文档里 `input_release_failed: true` 与 `outcome: BRIDGE_LOST` 同现（`cli/session_runtime.py:153/392/437`）；ledger 只有 Core 侧 `INPUT_RELEASED` 记账（`cli/session.py:1360-1385`）；Bridge 自己那条"IPC 丢失后释放了 N 个输入"的断言只存在于 1.21.4 的 CORE-060 能力集（`tools/assert_case_evidence.py:1597-1619`），V1201-040 没有 | **不成立**：1.20.1 没有任何独立工件证明停止阶段按键真的松开；registry 自己也写了这个缺口 `STOP_PHASE_EXPLICIT_KEY_RELEASE`（`reviewed-tested-bundles.json:42`，1.21.4 同样在 :133）。V04 当时已把声明缩到"lease 到期松键被记账"（主计划 :3561-3564、:3663-3665），因此**不是谎报，是能力边界** |
| A3 | `tested` 必须由可信 promotion 过程对**真实封存 bundle** 独立核验（V05 契约；`tools/report_promotion.py:7-10` 明说"只读只判、什么都不写，这里没有 registry"） | `tested` 是 V05 依 V04 封存材料**人工登记**（主计划 :3651-3657 `tested_registration_decision`）；`version_resolution.py:375-379/458-459` 只比较条目与自己 evidence 段（同一份文档内部），digest 只过正则 `:31`；`resolve()` `:752-836` 只看 protocol/os_arch/version_text/status，**不打开任何 bundle/jar/证据文件** | **不成立（作为自动校验）**：没有任何代码在运行时把 `tested` 的摘要与封存构件对照。条目引用的 4 个 `bundle_digest`（registry :46-83）在仓库里**只是文本**，真件在 `minekin-runner-data` 卷里 |
| A4 | 安装门必须"先核对被审摘要再装"（V06 `require_reviewed_plan`） | `provision.py:218-235` 确实**重算**：recipe 摘要由 `_reviewed_digest(recipe_path)` 现算（`:145-158`，CRLF 归一），launch plan 摘要由 recipe + 钉住 metadata 重建后比对；但 plan 里的 bridge 摘要是**硬编码常量** `recipe.py:71 BRIDGE_1201_JAR_SHA256`；jar 字节要到启动阶段才被真读真算（`recipe.py:435`，`require_built_bridge`） | **部分成立**：recipe/plan 两层是真算真比；**bridge 那层是常量搬运**，其可信度来自 V03 封存那一刻的真哈希（`bundle-candidate-1.20.1.json:40-41/3299-3300`），今天没有任何步骤把它从 jar 或 source tree 重算出来 |
| A5 | 握手必须按本次会话的 recipe 校验版本（V03/V04 契约；V04 记 `bridge_hello_version_defect`，主计划 :3410-3421） | `bridge-1201/.../BootstrapDescriptorAdapter.java:44-45` 与 `HandshakeGate.java:169` 写死 `1.21.4`/`0.16.9`；`ipc.py:437-438/628-629` 也按同两串字面量比；真实值是 `bridge-1201/gradle/libs.versions.toml:3/6` 与 `fabric.mod.json:17/20` 的 `1.20.1`/`0.19.5`，recipe 亦写 `:7/16` | **不成立**：1.20.1 客户端能过握手是因为它在 hello 里**谎报**版本。修它会让 `bridge jar sha256`、`source_tree_sha256`（`bundle-candidate-1.20.1.json:43`）、recipe 摘要（`manifest.sha256:22`）与 registry 条目全部失效，须重封并重判（`VERSION-BRIDGE-IDENTITY-001`） |
| A6 | V06 设计卡反例（磁盘写失败、原子 rename 失败、并发同 digest）要有可复判覆盖（主计划 :3884-3887） | 隔离与完整性失败有真文件系统覆盖（`test_artifact_store.py:44-54`、`test_artifact_fetch.py:97-118`、`test_bundle_install.py:145-197`）；但写失败/ENOSPC 注入=0 命中，`os.replace` 失败只在**证据包**发布器被测（`test_evidence_bundle.py:115-125`，非 store），`artifacts.py:176-177` 的 `FileExistsError → verify` 分支无测试 | **收卡口径有误**：V06 :3969-3970/:3953-3954 写"既有 store 契约覆盖"，实测这三类里两类无测试、一类只覆盖了别的模块。代码本身安全（可见性只经 `os.replace` 原子换名，`artifacts.py:151-182/240`），**缺的是证据不是实现** |

## 2. 判定：当前 `tested` 在两条用途上各自能不能用

- **本地受控运行（V07 已经这样用了）：可用，且已用对。** 依据是 A1/A4——真跑过的入服+移动+lease 松键读数，加上
  安装门对 recipe/plan 的真重算。边界必须一起说：A2 的停止阶段显式松键**未证**，A5 的握手版本是谎报。
  V07 的 `not_tested_v07` 已把 A5 列入，V09 的 look/move/**release** 闭环**不得**把 A1 当作 A2 的证明。
- **远程自动选择（V08）：不可用为充分证据。** `resolve()` 不校验封存摘要（A3），bridge 那层靠常量搬运（A4），
  而封存常量指向一个 `BridgeHello` 谎报版本的 jar（A5）。把远程入服交给这条链，等于把安全属性交给一份
  自述文本。审查门的结论就是：**V08 提升前必须完成 A5 的修复+重封+重判，以及 A3/A4 的独立校验**。

## 3. 确证缺口的登记（本提交只登记 `QUEUED`，提升须另一次独立提交）

1. `VERSION-BRIDGE-IDENTITY-001`（已在册 `QUEUED`）：修 hello 常量与 Core 期望值，重封 1.20.1 candidate；
   **重封后必须由新 run 重判 A5/A1/A4**，不得沿用 `9e162d83…`/`ac403160…`/`f552b92a…` 旧摘要。
2. `TESTED-PROVENANCE-VERIFY-001`（本记录登记）：把 A3/A4 变成机器事实——一条独立校验路径，对封存 jar 与
   source tree 真算 sha256，与 registry 条目对照，缺件或不符即拒。
3. `KEY-RELEASE-AT-STOP-001`（本记录登记）：补 A2，让 1.20.1 在停止/断连阶段有 **Bridge 侧独立**松键工件
   （CORE-060 那种），或按产品决策明确把该能力从 `tested` 声明里划出去。
4. `STORE-FAILURE-EVIDENCE-001`（本记录登记）：补 A6 的三类故障注入证据，并**更正** V06 收卡卡里"既有 store
   契约覆盖"这句口径（不改判据文字，只改事实陈述）。

## 4. 未做的事

没有改 registry、recipe、`manifest.sha256`、case JSON 或任何产品代码；没有连接用户远程服；没有把任何未证的
安全属性写成 PASS；`tools/report_promotion.py` 的"只读只判"契约保持不变。
