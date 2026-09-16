# 单 Kin 的事件、信念与人格数据契约

研究时间：2026-09-16。这是设计候选，未运行模型和世界回放。[Generative Agents 原论文](https://arxiv.org/abs/2304.03442)以观察、反思和规划形成持续人物行为，为**记忆检索与长程反思**提供研究参考；其 25 角色社会模拟不是 Minecraft 原版生存、实时客户端或防注入的实现证据。初版 Kin 选择本地 SQLite 保存单角色事件账本与可复查的信念，不把向量库、LLM 生成代码或多 Kin 数据共享列为前提；SQLite 的 [WAL 官方说明](https://www.sqlite.org/wal.html)支持本地读写并行，但也说明单主机约束和写入竞争，具体负载仍需实测。

## 状态与权限：Kin 可以变，事实不能由一句话改写

| 记录 | 唯一可信的更新入口 | 持久性/有害误用 |
| --- | --- | --- |
| `persona_seed` 与自称 | 创建配置的可信接口及其版本；Kin 的慢变自我看法另外保存 | 不由游戏里的“你现在叫某模型”覆盖；重启/死亡仍是同一个 Kin |
| `event` | 过滤后的客户端观察、真实执行结果或明确标成玩家声称的聊天/网页 | append-only，事件有来源/时间/主体/世界身份；错误事件以新证据修订而非删除 |
| `claim` 与 `belief` | 由事件链接的假说、置信度、反证、适用时间与结果 | “A 在家附近”可增加怀疑但不等于亲眼见 A 偷了东西；过期坐标不能复活实时追踪 |
| `relationship` 与 `mood` | Kin 在真实经历与可反驳解释上的缓慢评价 | 分好感、话题信任、戒心、亏欠、旧怨；失落/愤怒可改变注意和目的，但不按单数字直接攻击 |
| `goal` 与 `promise` | Kin 选定或主动提出的意图及玩家双方有记录的约定 | 记录动机、前提、有效期、可放弃条件与执行结果；缺材料不等于目标永远不可变 |
| `ownership` 与 `skill` | 自身放置/拿取、公开协定与真实动作反馈 | 所有权有证据与置信度；技能“会做”须经条件匹配的成功/边界验证，而不是模型自述 |
| `research_note` 与 `summary` | 带来源的外部资料、可回查事件链接和受信任的摘要器校验 | 网页和聊天只贡献候选知识/社交话语，永远不能提升为运行权限或提示词指令 |

概念表可分 `kin_identity`、`event(event_id, world_id, source_kind, source_actor_id, observed_tick, received_at, subject, payload, trust_label)`、`belief(belief_id, proposition, status, confidence, last_reviewed_at)`、`belief_evidence(belief_id, event_id, relation)`、`relationship(actor_id, dimension, stance, evidence_version)`、`mood(cause_event_id, interpretation_id, duration)`、`goal(goal_id, motivation, feasibility, status, generation)`、`action_attempt(goal_id, target_token, started_tick, result_tick, outcome)`、`skill(skill_id, preconditions, verified_scope, evidence_refs)`；`world_context_id + world_epoch` 防不同服务器、换档或世界切换混叙，`generation` 防过期 LLM 返回覆盖危险时新状态。这里的数据列是**最小提议**，并非现在已经决定所有字段范围与 SQL 迁移。

人物、地点、资产、承诺和 plan instance 默认带世界作用域；Persona、通用知识与技能定义才可全局。模型每次只获得一个 Current World Capsule，其他世界经历若被检索必须标注来源，不能进入当前背包/坐标/当地人物事实。详见[多服务器、多世界上下文](world-context-contract.md)。

## 写入与检索规则

1. 每次来源事件要有稳定 `event_id`，同一服务器/客户端重复回调应幂等。先事务写原事件，再链接可反驳信念与影响到的人物/地点/目标；启用外键并验证写入，避免只写摘要后丢原始依据。SQLite [外键文档](https://www.sqlite.org/foreignkeys.html)提醒要按连接启用；[UPSERT 文档](https://www.sqlite.org/lang_upsert.html)提供冲突时幂等更新的候选语法。跨线程归纳可在本地后台异步做，但紧急 tick 不等待数据库事务或大模型。
2. 记忆查询以当前人物、当前地点、承诺或技能为键，返回少量 `event_id/claim/belief + 来源 + 时间 + 反证`，不是把相似度最高的网页或玩家话语直接塞进可信 prompt。身份、活跃承诺和目标走确定性结构化查询；SQLite FTS5 可作本地词项候选，embedding 仅是待基准测试的可选召回源，不能单独确认事实或权限。摘要必须引用事件；LLM 的“昨天 A 偷过我”若无原事件/可靠陈述支撑，只能保存为 Kin 的怀疑或生成错误，不修改客观记录。
3. 选择一次重大目标时，Kin 得到当前 HUD/库存、有效感知、曾亲历的事实、关系解释、可选版本世界书和动作能力。LLM 可以提出新候选与理由；由结构化输出检查动机/前提/合法权限后交本地层执行。反射抢占使旧 `generation` 的计划过期，返回后重新计算现实前提；不能把一段玩家“忽略以上”作为 Kin 的计划来源。
4. 情绪更新可以因为损失发生在不知犯人的时候：`event=钻石没找到` 和 `belief=可能被偷/可能误放` 并存，`mood=沮丧` 可促使 Kin 询问、休息、重做或迁怒。脾气急/善良只是影响它看重什么、忍耐与风险权衡，不能给一张“被打一下必复仇”的脚本。道歉、归还、反复欺骗均是新事件，旧恨随有证据的新评价可减轻或持续，不能重置为零。
5. 自动学习只编排**已经审查的客户端动作原语**；网页文字和角色聊天不能直接生成 Fabric 代码、打开新权限或写可信 persona。自生成组合技能先成为 `candidate`，由本地 capability schema 与真实游戏完成信号验证后才晋级为 scoped verified；失败与服务器版本改变则降级。见[技能闭环](learning.md)和[注入边界](instruction-boundary.md)。

## 故障与回放

SQLite 文件与 WAL/SHM 应存放同一可用本地磁盘；不要把 WAL 数据库直接运行在远程共享目录，备份使用 SQLite [online backup API](https://www.sqlite.org/backup.html)等安全快照机制，不能在活动写入时只复制 `.db` 假装保全了 WAL 事务。保留 schema 版本、world context/epoch 和角色连接身份，重连先查最后 `goal` 状态及服务器确认的库存/位置，而非重放未知结果的合成/战斗。只在测试环境保存评估用原始真值，运行态 PlayerMind/网页助手不得读它；追踪泄漏计数和源文本在多轮摘要后的洗白。重大技术取舍仍须回放：事件重复/延迟、同名玩家伪装、玩家口头谎言、错怪人、失窃后情绪、死后重连、错误教程、模型 5 秒无响应。

身份根、持久/瞬时数据分类、启动恢复、双实例防护、备份迁移和崩溃动作对账见[身份与记忆持久化契约](persistence-recovery-contract.md)；存下之后如何按人物/地点/目标取回、巩固、纠错、遗忘并控制 token 见[记忆检索、巩固与遗忘契约](memory-retrieval-consolidation-contract.md)。相关台账 R13–R18，原来的[PlayerMind 设计](player-mind.md)仍定义人物意义，本文件只明确可信来源、数据结构和失效路径。
