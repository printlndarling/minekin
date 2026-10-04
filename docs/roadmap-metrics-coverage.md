# Roadmap 衡量方式的词面覆盖（第一遍）

更新：2026-10-04（基线 `78ef18d`）。这是 F 阶段"指标 → 判定位置"对照的**第一半**：只回答"这些名字现在出现在仓库哪里"，不对"概念有没有承载"作推断。

方法：从 [roadmap.md](roadmap.md) 的「衡量方式」表机械取出 50 个指标名，对全部受跟踪文件做 `git grep -l -F <name>`（词面匹配；`roadmap.md` 自身不计，命令可复现）。

读数：**50 个名字里 47 个只出现在 roadmap.md 里**；3 个在别处逐字出现：

| 指标 | 逐字出现处 |
| --- | --- |
| `event_to_input_ticks` | [headless-client-media-contract.md](headless-client-media-contract.md) |
| `unauthorized_read_count` | [perception-implementation.md](perception-implementation.md) |
| `belief_leak_count` | [perception-implementation.md](perception-implementation.md) |

其余 47 个（词面未在别处出现）：

`p0_evidence_bundle`、`remote_admission_trace`、`offline_session_trace`、`managed_storage_trace`、`hosted_world_trace`、`host_control_trace`、`host_commit_trace`、`runtime_bridge_trace`、`world_context_trace`、`dashboard_observer_trace`、`live_view_trace`、`bundle_supply_chain_trace`、`identity_admission_trace`、`auth_secret_exposure_trace`、`render_media_isolation_trace`、`reflex_success_rate`、`stale_intent_rejected`、`instruction_boundary_trace`、`exception_usage_trace`、`claim_evidence_trace`、`perception_mode_trace`、`goal_progress`、`choice_context_trace`、`bootstrap_action_trace`、`site_choice_trace`、`memory_retrieval_trace`、`social_consistency`、`emotion_action_trace`、`attribution_accuracy`、`memory_revision_trace`、`persistence_recovery_trace`、`research_to_action_trace`、`mode_lifecycle_trace`、`personality_continuity`、`decision_agency_trace`、`starter_relationship_trace`、`persona_creation_trace`、`persona_behavior_trace`、`domain_knowledge_trace`、`ability_growth_trace`、`attention_intent_trace`、`goal_horizon_trace`、`world_guide_accuracy`、`learning_reuse_trace`、`skill_invocation_trace`、`repeat_failure_rate`、`model_cost_and_latency`

## 怎么读这张表（别把词面当承载）

- 词面未出现**不等于**没有承载：实现里这些量多数以别的拼写存在（例如成本与调用量记在 run 文档 mind 段的 `model_calls` / `model_spent_micro` / `model_cap_refusals`；动作链以 `steps[]` 与 `result/reason` 落账；封存侧是 bundle / registry / case 机制而不是指标名）。
- 词面未出现也**不等于**已满足：名字里承诺的维度（按 version/来源/陈旧度/分布而非均值等）是否真的进了字节，必须逐项核对，不能因为有一个近似字段就算数。
- 因此这张表只是**名册与词面**：它是逐指标对照的输入清单，不是覆盖结论。

## 下一步（F 阶段整卡）

逐指标建"名字 → 具体承载处（文件/字段/测试/case）→ 状态（已承载 / 部分（具名缺哪一维）/ 未承载）"对照。可从三类已知承载家族起步：①证据与轨迹类（bundle / registry / case + run document 各段）；②心智与社交类（mind 段字段与对应契约、单测）；③成本与延迟类（`model_calls` / `model_spent_micro` / 时间戳）。逐项核对后把本文件并进去，成为 F 收口的对账物。
