# Qoder 临时执行交接（2026-09-24）

本文件是主控对当前执行者的具体工作单，不替代
[`development-execution-plan.md`](development-execution-plan.md) 的唯一 `NEXT`、
[`p0-remote-admission-contract.md`](p0-remote-admission-contract.md) 的判据或用户指令。
审查固定点为 `d3a4064d53bf3cc79ed4b2540c41c697a17049a2`；已提交 HEAD
为 `18219c6ad5db7a4af106bc1e95675aeac7ca14d1`。HEAD 之后还有未提交的
`ADMIT-070-REFUSAL-INJECTION-001` 改动；这些改动属于进行中，不是 DONE。

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
- 远端 `codex/core-state-transition` 为 `18219c6`，远端 `main` 仍为 `25a9868`；
  两者差 7 个已提交阶段。分支已推送不等于计划要求的 `main` 已推送。

## 当前唯一执行卡：ADMIT-070-REFUSAL-INJECTION-001

Qoder 只处理执行计划该卡列明的 `allowed_paths`；不要同时做
`ADMIT-070-CASE-001`、HOST/PERSIST、CI 或认证方式扩展。你不是唯一在代码库工作的
执行者；保留其他人的改动，不要 reset、stash、覆盖或改写既有 sealed bundle。

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
   当前分支；`main` 必须在独立审查确认通过后 fast-forward 并核对远端 SHA。
   Qoder 不得改 `current_next` 或任务 `status`，也不得自行把 campaign 标成 DONE；
   将原始命令结果、run ID、digest 与 commit SHA 交给主控，由主控更新计划。

## 下一阶段（仅主控排队，当前不得领取）

当前卡通过、commit/push 且经主控复核后，主控才登记/提升
`ADMIT-070-CASE-001`：从同一 sealed bundle 交叉核对 JOIN、Core 的
`NOT_AUTHORITATIVE` 拒绝、0 准入、无 PLAYABLE/lease、generation 终止和注入归因；
针对缺 JOIN、无真实拒绝、错 run/代、只有日志、缺注入记录逐个做 FAIL 变异；
再运行 evidence verify、hermetic rejudge、适用 replay、promotion 一致性检查。
随后才回到 campaign 的 OFF-A/OFF-B 场景。HOST 与 PERSIST 的决策卡仍不能由
执行者猜测结论。
