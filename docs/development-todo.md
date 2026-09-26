# 当前开发 TODO（短入口）

更新：2026-09-26。唯一状态源是[执行计划](development-execution-plan.md) 的 `current_next`；本页仅便于看进度。此前 3601 行已完成事项、原始读数和 Qoder 未提交的第七类审计草稿保存在[历史 TODO](development-todo-history-through-cef712b.md)，没有丢弃。

## 当前

- [x] `DONE`（2026-09-26）：`V1201-LOCAL-DEMO-REHEARSAL-001`。全新 data root/全新 Kin 的一次自动路径 run 接成 sealed PASS：装机 3639/3639、同 generation 的 look+move 与到期释放、退出；四读一致，七类反证各自变红，两次失败 attempt 保留。读数与缺口见[执行计划 §2](development-execution-plan.md#2-上一卡交付与当前-next-边界)。
- [x] `DONE`（2026-09-26）：`V1201-LOCAL-NEGATIVE-MATRIX-001`。六族逐族量出当前 build 的可重跑拒止与 sealed 重读：18 行真 socket 状态探测 `FAIL=0`、自动入口两条 `NEEDS_PIN`、装载期禁区地址四拒（含"拒在发出字节之前"的连接计数证明）、显式路径五拒 + Bridge 钉错两拒、`V1201-060/070/080` 本 build `PASS / agrees`。逐行读数与配对反证见[负向矩阵复判记录](version-negative-matrix-2026-09-26.md)。
- [x] `DONE`（2026-09-26）：`V1201-TESTED-GATE-READOUT-001`。规范卷只读复判：provenance `verified / rc=0`、六条 1.20.1 引用四读一致且全归当前 build、19 能力与六 case 断言双向差集为空、promotion 三门仍 `false`（`CASE_VERSION_MISMATCH`/`NO_MANDATORY_CASES`）、卷内 15 次 attempt 的引用与失败分布已列清；四条反转（缺件/摘要改一位/空根/删工件）证明读者能判红。边界与读数见[复判记录](tested-gate-readout-2026-09-26.md)。
- [x] `DONE`（2026-09-26）：`P0-EVIDENCE-INVENTORY-001`。规范卷只读四桶盘点：`missing_fixture 31 / no_current_build_evidence 28 / real_failure_on_current_build 0 / current_build_pass 15`（74 条恰落一桶），11 门 block 与三种 block 语义分开，产品未实现只在缺 fixture 侧点名 6 条整条 + 2 个半句，HOST 18 条不判；四条反证各移一个机制（删 fixture / 空根 / 改判 `FAIL` / 改一位摘要），真件八条自检 `FAIL count = 0`。盘点不点亮任何门。逐条读数见[盘点记录](p0-evidence-inventory-2026-09-26.md)，排卡见[执行计划 §3.3](development-execution-plan.md#33-b1-交出的缺-case-排卡按-12-单独登记不由-b1-顺手写断言也不自占队列)。
- [x] `DONE`（2026-09-26，B2 的第一刀）：`P0-CORE-040-050-RUN-001`。`CORE-040`、`CORE-050` 各在**当前构建**上补了一轮受控本地 dedicated offline 真跑并封证：两条判绿行四读齐全（verdict / `evidence verify` / `report_promotion` row / 独立复判 `6/6`、`4/4`、`disagreements=[]`），`case_version` 逐字节等于今天的摘要、`from_repository_build: true`；W60 读数转为 `promotable: true / blocks []`（**仅机器候选，不晋级**），`p0-core` 只剩 `REQUIRED_CASE_NOT_REGISTERED`。`CORE-050` 第 1 次 attempt 因本次命令漏 `STILL=1` 真实 FAIL 并保留。反证四组（撤任一 run ⇒ 门红；改一位封进去的字节 ⇒ `EVIDENCE_NOT_VERIFIED` + `rc=12` + 复判拒判，规范卷不受影响）。读数见[第一刀记录](p0-core-040-050-run-2026-09-26.md)。
- [ ] `NEXT`：`P0-CONTROLLED-CAMPAIGN-001`。B 段第二张：在受控 dedicated offline 与必要 LAN 场景补当前 build 的 mandatory sealed bundle。**第一刀（`CORE-040`、`CORE-050`）已完成，卡片仍在进行**；剩余是 `OFFLINE-030`、5 条只有别的构建 bundle 的 `ADMIT-001/040/060/100/110`，以及卡面后半段 L3/L5/L6、崩溃恢复、重启协调、offline identity 与 soak。
- [ ] `QUEUED_PROPOSED`（B1 交出，等主控排期）：`P0-OFFLINE-090-100-EVIDENCE-CHECK-001`（甲类：字节已封、缺 case 定义与断言；Dashboard 那半句要登记为材料外边界）。
- [ ] `BLOCKED_DECISION`（B1 交出，缺的是选择不是代码）：账本是否承载 profile/endpoint（`ADMIT-010/020`）、人格未重建的承载（`ADMIT-090`）、oracle/canary containment 来源（`ADMIT-120`、`CORE-080`）、OFF-D/OFF-N 是否进候选集（`OFFLINE-060`）、`identity_revision` 变更事件（`OFFLINE-070` 半句）、封禁是否独立分类（`OFFLINE-080` 半句）、`ADMIT-030/050` 的 case id 拆分。执行侧不自造断言。
- [ ] `QUEUED`：`V1201-AUTO-PATH-RUNNER-001`。让自动解析与服务端读数在受控通道里同时成立（A1 的 G1/G2）。
- [ ] `QUEUED`：`V1201-AUTO-ENTRY-GATE-ORDER-001`。把 loopback-only join 授权与 profile 版本 allowlist 移到任何下载之前（A2 的 N1）。
- [ ] `QUEUED`：`V1201-MAX-BYTES-VALIDATION-001`。非正预算要具名拒止而不是 `INTERNAL_INVARIANT`；`--max-bytes` 与 `--profile` 同给要具名用法错误（A2 的 N2）。
- [ ] `BLOCKED_DECISION`：`V1201-DISK-PREFLIGHT-001`（A2 的 N3，磁盘不足的失败类别未冻结）与 `V1201-SRV-RESOLVER-001`（A2 的 N4，是否引入 DNS/SRV 解析）。
- [ ] `BLOCKED_DECISION`：`V1201-DEMO-CASE-FREEZE-001`（A1 的 G3）——融合演示 case 断言哪些事实，含 040/080 两种释放原因在同 run 互斥；须主控冻结，执行侧不自造断言。
- [ ] `BLOCKED_DECISION`：V08 对用户 1.20.1 测试服的一次只读探测和非破坏性入服，须新的本次许可；之后 V09 动作须单独限幅授权。V10 依赖真实 V08/V09。
- [ ] `BLOCKED_DECISION`：HOST §5 三格所有权；PERSIST case 冻结；残留进程处置；数据保留/删除。不要猜。
- [ ] `BLOCKED_EVIDENCE`：`P0-GATE-PROMOTION-001` 与各门晋级——`promotable` 只是机器候选， mandatory 真实证据（现由 `P0-CONTROLLED-CAMPAIGN-001` 承接）补齐前不用单测或旧包替代。**读数已变（2026-09-26）**：`report_promotion` 对 W60 给 `promotable: true / blocks [] / requirement.satisfied: true`，即它那 7 条 mandatory 全部满足（其中 `CORE-040`、`CORE-050` 两条是本卡补的，其余 5 条在 B1 的 baseline 上就已满足）；是否晋级仍是主控决定，不由本读数触发。

## 后续阶段索引

执行计划 B：P0 完整门禁与平台矩阵；C：HOST 真实双客户端和存储/恢复；D：PERSIST 与运维策略；E：Harness/Dashboard、导航/生存、长期自治/记忆、社会交互、单 Kin 完整 demo、远期多 Kin/跨维度。每阶段的依赖、验收和阻断都在[执行计划](development-execution-plan.md#4-完整-minekin-长程任务簿设计先行证据后置)。[产品场景路线图](roadmap.md)仍是范围基准，不把已完成的 P0 层误报为整个项目完成。

本页不再追加逐次历史 run 日志；新卡证据记录在卡或独立 evidence 索引，封存件在规范数据根，摘要和 commit 可追。旧档只读。
