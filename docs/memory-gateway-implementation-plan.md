# 记忆子系统实施设计（S2-MEMORY-GATEWAY-DESIGN-001）

状态：实施设计（2026-10-06，基线 `6c3f1be`）。上位契约是
[记忆检索、巩固与遗忘契约](memory-retrieval-consolidation-contract.md)；本文不重述契约，
只回答"按什么顺序、以什么形状把它落到本仓库"，并给每个切片标注**消费方**与**判据**。
契约里的设计结论（存着不等于想得起／带出处的证据／遗忘不改写历史／信任标签跨层保留／
本地检索优先／固定上下文预算／LLM 可建议不能权威写入）在没有逐条讨论时**原样成立**。

## 1. 现状（代码核验，2026-10-06）

已有：
- 事件账本（kin sqlite，append-only，带 `source`/`trust_class`/`payload_hash`）；
- 恢复包 `last-session-v1`：上次 run 的相位、`input_release`（nothing_held /
  released_recorded / not_released / unknown，digest+顺序+generation 校验）、
  `server_profile_id` 与 `current_world_applicability`；技能经验 `skill-experiences-v2`
  （按技能聚合的结果/原因模式，带 freshness/applicability 标签）；
- persona（种子可复现 + manifest）与模型 offer 的证据纪律（系统提示明说历史≠现状≠许可）。

没有：按锚点（人物/地点/目标/时间）的情节检索；`MemoryContextPacket`；承诺；信念/关系
存储；网关写路径（模型文本→记忆的任何通道）；上下文预算的显式"省略了什么"。

## 2. 落库形状（决定，先于任何编码）

1. **情节事件＝现有事件账本**，不另起第二本：`SkillStepRecorded`、`InputReleased`、
   `SessionStateTransitioned` 等已经有信任标签与 digest 纪律。新增种类才写新事件类型。
2. **物化信念/承诺＝各自的表**（后续切片），行必须携带支持/反对事件引用与版本；
   禁止无证据行。
3. **读路径先行、写路径后到**：读只碰账本/表，永远不产生"故事"；写路径（网关）只在
   切片 B/C 出现，且只接受两类写者——Core 自己（既有）与**经校验的候选记录**
   （模型建议也走后者，`trust_class=MODEL_SUGGESTED`，schema+证据引用+预算校验后才落）。
4. **检索一律确定性键优先**（kin/run/goal/事件类型/位置序），embedding 不在首版。

## 3. 切片排序（含消费方与判据）

### 切片 A（可立即建）：目标域情节召回 `recall_goal_history`

- **先补一格写侧（核验发现）：** 今天的 `SkillStepRecorded` payload 不带产物——
  按产物检索无从谈起。切片 A 先给 payload 加一个有界的 `product_id` 字段：值取
  步骤**自己 outcome.details 里**的产物（craft 类步骤有；没有的写空），
  CORE 来源、单字段、不改既有键（先红后绿钉住 payload 形状）。
- **形状**：`recall_goal_history(database, kin_id, product_id, exclude_run_id, limit)` →
  有界 packet：按位置倒序的最近 N 条**产品相关**结果（`product_id` 命中的步骤，含技能、
  结果与原因），每条带 `run_id`/`position`/`result`/`reason`/`observed_at_utc`/
  `source`/`trust_class`；没有命中 → `status: "not_retrieved"`（**不是空故事**）；
  损坏行跳过并计数（`skipped_unreadable`），不使整包失败；扫描上限沿用
  `skill_history.py` 的 `scan_limit`/`records_omitted_within_scan` 先例。
- **消费方（真实存在）**：心的决策输入——今天的 `skill_experiences` 是**按技能**聚合，
  回答不了"为这个目标我最近试过什么、停在哪"；目标域召回直接进摘要的
  `session_history`，让模型在重复失败路线上改道（首版唯一有现成消费方且不改写者的切片）。
- **判据**：单测（写侧 payload 形状钉；读侧有/无命中、损坏行跳过、跨 run 只认锚点、
  只读不写字节不变）；活体读数等窗口（模型在摘要里引用历史失败并改道的理由逐字）。
- **不做**：不写任何表；不改模型 offer 的系统提示（现有纪律已覆盖"历史≠现状"）。

### 切片 B（需要写者治理）：承诺

- 写者＝模型建议经网关校验（候选 schema：`commitment`/`evidence_ref`/`due?`），
  Core 侧建表 + resume 装载"未完成承诺及期限"；触发"记得但要重验"的阅读规则。
- 消费方：下一会话的目标/计划与恢复包。判据：候选拒绝矩阵（无证据/越权/超预算），
  重启后承诺仍在、且不作为动作许可。

### 切片 C（等社交/地标面）：人物与地点的信念

- 依赖玩家聊天身份面与地标观察（S3-SOCIAL / 世界上下文契约）；先有观察才谈巩固。
- 遗忘策略（降优先级、标记陈旧）在此切片随信念版本一起落。

## 4. 明确不做与仍未知

- 不做 embedding/向量召回（契约首版不依赖；保持纯确定性）。
- 不做模型文本的原文持久化；建议永远只有"候选+引用"。
- 未知：跨世界命名空间的记忆作用域规则（`current_world_applicability` 已有三态，
  但"同 profile 不同存档"没有可比键）；情节保留期限与预算数值——等到切片 A 的
  真实读数再定，不预填。

## 5. 与现行纪律的接口

- 模型 offer：任何新字段进 offer 前过 `BEHAVIOR_PARAMETERS`-式的声明与系统提示纪律；
- 审计：切片 A 的 packet 只出现在摘要/文档，不写账本；切片 B 的每次接受/拒绝写
  事件（`source=CORE`，`payload` 带候选引用）；
- 所有权：本文件不改变任何 `current_next`；切片 A 的画卡时先核 `skill_history.py`
  是否有可复用的扫描纪律（`scan_limit`/`records_omitted_within_scan` 已有先例）。
