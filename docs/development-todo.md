# 当前开发 TODO（短入口）

更新：2026-09-26。唯一状态源是[执行计划](development-execution-plan.md) 的 `current_next`；本页仅便于看进度。此前 3601 行已完成事项、原始读数和 Qoder 未提交的第七类审计草稿保存在[历史 TODO](development-todo-history-through-cef712b.md)，没有丢弃。

## 当前

- [x] `DONE`（2026-09-26）：`V1201-LOCAL-DEMO-REHEARSAL-001`。全新 data root/全新 Kin 的一次自动路径 run 接成 sealed PASS：装机 3639/3639、同 generation 的 look+move 与到期释放、退出；四读一致，七类反证各自变红，两次失败 attempt 保留。读数与缺口见[执行计划 §2](development-execution-plan.md#2-上一卡交付与当前-next-边界)。
- [ ] `NEXT`：`V1201-LOCAL-NEGATIVE-MATRIX-001`。复用既有负例，只补真实组合缺口。
- [ ] `QUEUED`：`V1201-TESTED-GATE-READOUT-001`。规范卷和当前构建的 tested/provenance/风险边界报告。
- [ ] `QUEUED`：`V1201-AUTO-PATH-RUNNER-001`。让自动解析与服务端读数在受控通道里同时成立（A1 的 G1/G2）。
- [ ] `BLOCKED_DECISION`：`V1201-DEMO-CASE-FREEZE-001`（A1 的 G3）——融合演示 case 断言哪些事实，含 040/080 两种释放原因在同 run 互斥；须主控冻结，执行侧不自造断言。
- [ ] `BLOCKED_DECISION`：V08 对用户 1.20.1 测试服的一次只读探测和非破坏性入服，须新的本次许可；之后 V09 动作须单独限幅授权。V10 依赖真实 V08/V09。
- [ ] `BLOCKED_DECISION`：HOST §5 三格所有权；PERSIST case 冻结；残留进程处置；数据保留/删除。不要猜。
- [ ] `BLOCKED_EVIDENCE`：P0 campaign/当前 build mandatory 真实证据；按主计划 B 段排入，不用单测或旧包替代。

## 后续阶段索引

执行计划 B：P0 完整门禁与平台矩阵；C：HOST 真实双客户端和存储/恢复；D：PERSIST 与运维策略；E：Harness/Dashboard、导航/生存、长期自治/记忆、社会交互、单 Kin 完整 demo、远期多 Kin/跨维度。每阶段的依赖、验收和阻断都在[执行计划](development-execution-plan.md#4-完整-minekin-长程任务簿设计先行证据后置)。[产品场景路线图](roadmap.md)仍是范围基准，不把已完成的 P0 层误报为整个项目完成。

本页不再追加逐次历史 run 日志；新卡证据记录在卡或独立 evidence 索引，封存件在规范数据根，摘要和 commit 可追。旧档只读。
