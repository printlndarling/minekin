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

## 第二半 · 族①（证据与轨迹）第一遍

只写本遍**用指针核过**的承载；没核到的写"本遍未核到"，不猜。状态口径：**有字节**＝契约/工具/case/run 文档里能指到；**契约在、实现未接**＝设计已冻结、按阶段表尚未实现；**待决策**＝保留事项。

| 指标 | 承载处（本遍核过） | 状态 |
| --- | --- | --- |
| `p0_evidence_bundle` | [p0-validation-evidence-contract.md](p0-validation-evidence-contract.md) + `tools/seal_run_evidence.py` / `assert_case_evidence.py` / `check_case_assertions.py`（151 registered）/ `report_promotion.py` + registry `tests/fixtures/registry/reviewed-tested-bundles.json` | 有字节（封存/校验/晋级链） |
| `remote_admission_trace` | `docs/validation/` 入服系列（join / local-join / lan-joiner）+ `tools/run_controlled_server.py` + 封证 case | 有字节；具名缺：LAN 第二客户端同 run 封证仍为 0 |
| `offline_session_trace` | [launcher-supply-chain-contract.md](launcher-supply-chain-contract.md) 与离线 profile 冻结记录 + validation 文档 | 有字节（离线）；在线认证一侧待决策 |
| `managed_storage_trace` | [managed-client-runtime.md](managed-client-runtime.md) + runner `kin_lock.sh`（单写锁） | 有字节 |
| `hosted_world_trace` / `host_control_trace` / `host_commit_trace` | [hosted-world-storage-lifecycle-contract.md](hosted-world-storage-lifecycle-contract.md) / [hosted-world-control-boundary-contract.md](hosted-world-control-boundary-contract.md) / [hosted-world-commit-recovery-contract.md](hosted-world-commit-recovery-contract.md) | 契约在、实现未接（HOST/PERSIST 待决策） |
| `runtime_bridge_trace` | [runtime-ipc-deployment-contract.md](runtime-ipc-deployment-contract.md) + [input-arbitration-contract.md](input-arbitration-contract.md) + run 文档 release/lease 读数 | 有字节 |
| `world_context_trace` | [world-context-contract.md](world-context-contract.md) | 契约在、A→B→A 实测归 S7 |
| `dashboard_observer_trace` | [gateway-dashboard-readonly-contract-2026-09-28.md](gateway-dashboard-readonly-contract-2026-09-28.md) + 2026-10-04 真实网关浏览器读数（23 passed / 6 skipped） | 有字节（只读部分）；媒体故障隔离随媒体侧 |
| `live_view_trace` / `render_media_isolation_trace` | [headless-client-media-contract.md](headless-client-media-contract.md) | 契约在、媒体旁路实现未接（S1-E 已具名） |
| `bundle_supply_chain_trace` | `tools/verify_supply_chain.py` / `fetch_bundle.py` + [launcher-supply-chain-contract.md](launcher-supply-chain-contract.md) + bundle registry | 有字节 |
| `identity_admission_trace` | [stable-player-name-2026-09-29.md](stable-player-name-2026-09-29.md) + 后台身份读写/审计 + 入服文档 | 有字节（离线身份）；在线认证待决策 |
| `auth_secret_exposure_trace` | —（在线认证未启用） | 待决策 |

族②（感知/反射/安全：`reflex_success_rate`、`stale_intent_rejected`、`unauthorized_read_count`、`belief_leak_count`、`event_to_input_ticks`、`instruction_boundary_trace`）与族③（mind/社交/学习/成本）留下一遍；`event_to_input_ticks` 的词面承载已在 [headless-client-media-contract.md](headless-client-media-contract.md)、反射窗口契约在 [reflex-latency-contract.md](reflex-latency-contract.md)，逐项状态待核。

## 第二半 · 族②（感知/反射/安全）与族③（mind/社交/学习/成本）第一遍

同一口径：只写本遍核过的指针；未核到者留白。

| 指标 | 承载处（本遍核过） | 状态 |
| --- | --- | --- |
| `reflex_success_rate` / `stale_intent_rejected` / `event_to_input_ticks` | [reflex-latency-contract.md](reflex-latency-contract.md)（`event_to_input_ticks` 词面另见 [headless-client-media-contract.md](headless-client-media-contract.md)；`src/` 本遍未见 reflex 实现） | 定义在、实现未接 |
| `unauthorized_read_count` / `belief_leak_count` | [perception-implementation.md](perception-implementation.md) 把两者写成回放验收**必须分别报告**的项；可见性边界本体由 `domain/perception.py` 与 `tests/unit/test_perception.py` 承载 | 验收定义在；具名计数器未实现（本遍未核到计数字段） |
| `instruction_boundary_trace` | [instruction-boundary.md](instruction-boundary.md) | 契约在、实现未接（src/tests 本遍未见逐字承载） |
| `model_cost_and_latency` | 成本侧：mind 文档 `model_calls` / `model_spent_micro` / `model_cap_refusals`（player_mind 组装）+ 端点超时配置 | 有字节（成本）；延迟分布的统计本遍未核到 |
| `bootstrap_action_trace` | run 文档 `steps[]`（`result`/`reason`/`attribution`/`decision_source`）与历史活体 CONFIRMED 读数 | 有字节（部分；"中断后恢复"维本遍未核） |
| `repeat_failure_rate` / `skill_invocation_trace` | `record_result` 的归因/额度/`excluded_skills`/`last_precondition` 机制与其单测；"自主提炼组合技能"未见实现 | 部分（调用/回退/修订侧有字节；提炼未接） |
| `memory_retrieval_trace` | `adapters/sqlite/skill_history.py`（`read_skill_experiences`）→ `session_history.py` 组装进模型上下文；后台经历面板（2026-10-04 真网关读数）；[memory-retrieval-consolidation-contract.md](memory-retrieval-consolidation-contract.md) | 部分（技能经历/重启检索有字节；人物/地点/陈旧度维未接） |
| `persona_creation_trace` / `persona_behavior_trace` | `adapters/filestore/persona_store.py` + 后台人格展示 + persona 输入来源 trace | 部分（存储/展示/trace 侧有字节；生成器 seed/复现矩阵本遍未核） |
| `goal_progress` / `decision_agency_trace` | run 文档 `goal_met`/`stop_reason`/milestone 与 `decision_source`/`model_refusal`/改线读数 | 部分（目标达成与决策来源有字节；"自主产生/修改目标的依据、运行者请求与目标劫持对照"未接） |
| 其余社交/记忆/学习/日程类（`personality_continuity`、`starter_relationship_trace`、`social_consistency`、`emotion_action_trace`、`attribution_accuracy`、`memory_revision_trace`、`goal_horizon_trace`、`choice_context_trace`、`site_choice_trace`、`domain_knowledge_trace`、`ability_growth_trace`、`world_guide_accuracy`、`learning_reuse_trace`、`research_to_action_trace`、`mode_lifecycle_trace`、`attention_intent_trace`、`claim_evidence_trace`、`exception_usage_trace`、`perception_mode_trace`） | 契约/设计在：[persona-generation-contract.md](persona-generation-contract.md)、[memory-retrieval-consolidation-contract.md](memory-retrieval-consolidation-contract.md)、[social-attribution-contract.md](social-attribution-contract.md)、[decision-agency.md](decision-agency.md)、[attention-intent.md](attention-intent.md)、[learning.md](learning.md)、[world-guide.md](world-guide.md) / [world-guide-implementation.md](world-guide-implementation.md)、[research-skill-contract.md](research-skill-contract.md) | 定义在、实现未接（S5/S6；逐项指针本遍未一一核） |

至此 50 个指标名都有一行落点（有字节 / 部分 / 定义在-未接 / 待决策 / 本遍未核到）。原 10-04 第一半的"47 个只在 roadmap.md 出现"仍成立——本对照用的是**概念与指针**，不是词面。

## 下一步（F 阶段整卡）

三族第一遍已于 2026-10-04 走完：50 个名字各有落点（有字节 / 部分 / 定义在-未接 / 待决策 / 本遍未核到）。剩下的工作不是"建对照"而是"把每条落到可复核的字段与测试名"：逐项深核标着「部分」与「本遍未核到」的维度（延迟分布、具名计数器、中断恢复、生成器复现矩阵等），在 F 收口时把本文件作为对账物一并闭合。
