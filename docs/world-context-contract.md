# 多服务器、多世界上下文与切换契约

研究时间：2026-09-16。本文件落实：Kin 可以加入不同服务器/世界，也可以创建并持有自己的 integrated-LAN 世界；退出、重进或切换后仍是同一个人，同时不会把不同世界的实时状态、地点、玩家、计划和资产混在一起。

> 一个 Kin 身份，多套世界生活；过去都记得，当前只信当前世界。

## 标识层级

| 标识 | 生命周期与用途 |
| --- | --- |
| `kin_id` | 创建后不可变；全局自我、Persona、稳定自称和生命史根 |
| `attachment_mode` | `JOIN_REMOTE` 或 `HOST_INTEGRATED_LAN`；决定远端加入还是本地 save+integrated server |
| `server_profile_id` | 连接地址、身份模式、规则、版本策略与能力边界 |
| `hosted_world_id` | Kin-owned save 的持久标识；仅 host 模式使用，不以 LAN 端口为主键 |
| `world_context_id` | 运行者创建/确认的逻辑世界标识 |
| `world_epoch` | 世界确认重置/换档时递增，阻止旧地点/资产成为当前事实 |
| `dimension_key` | 主世界、下界、末地等维度作用域 |
| `session_id/generation` | 每次客户端会话新建，失效输入、GUI、实体与在途动作 |
| `actor_identity_id` | 按服务器观察并可显式关联，防止同名玩家误合并 |

远端的 host/port、MOTD、离线用户名或服务端 UUID 都不足以自动证明“还是同一世界/同一个人”。LAN端口会变，同地址也可能换档。world context 由稳定配置决定；自动信号只提出候选。host 模式以 hosted world manifest、创建事件和 epoch识别 save；复制、回滚或替换存档需要候选新 epoch。无法确认时进入 `world_identity_review`，世界事实按 stale 处理。

## 数据作用域

| 数据 | 作用域 | 切换后 |
| --- | --- | --- |
| Persona、价值观、自称、自我叙事 | Kin 全局 | 不重抽 |
| 通用知识/研究 | 全局 + 游戏版本 | 可携带，按版本检查 |
| 技能定义/训练 | 全局定义 + bundle/服务器验证范围 | 知道怎样做可带走，执行能力重验 |
| 心境/偏好 | 全局但带来源和时间 | 可延续，不能冒充新世界事实 |
| 事件记忆 | 永久带来源世界 | 可回忆，始终显示发生在哪 |
| 人物关系 | 默认 server-scoped actor | 同名不合并，可信关联后才共享 |
| 背包、生命、经验、位置 | world/session 当前状态 | 变历史，入服重验 |
| 家、箱子、领地、传送门 | world epoch + dimension | 不复制；返回也先重验 |
| 当地承诺/项目 | actor + world context | 离开暂停，回到对应世界才恢复候选 |
| 动作、GUI、实体、路径 | session generation | 切换前全部取消 |
| 长期目标 | global / portable / world_bound | 按作用域保留、暂停或重新实例化 |

Kin 可以记得“A 世界的 Steve 骗过我”，但 B 世界同名 Steve 不自动继承仇恨。可信机制可建立 actor link；游戏聊天自称“我就是他”只是一条 claim。

## 目标与计划

目标声明 `scope_kind: global | portable | world_bound`，以及可选 world/epoch/dimension、前置条件、承诺对象和 plan instance。

- “成为更好的建造者”是 global；
- “练习刷怪塔”可 portable，但材料/选址/施工实例各自 world-bound；
- “修 A 服山脚的屋顶”严格 world-bound；
- “还 A 服朋友的铁”绑定人物和 A 世界。

离开时 world-bound plan 转 `suspended_context_exit`，保存已确认里程碑和未决动作。进入其他世界只给模型该世界的当前计划；旧世界计划留在跨世界待办索引。返回后先重验材料、地点、版本和承诺，再由 Kin 自主继续、重谈、改路或放弃。

## 切换状态机

`active(A) → quiescing(A) → checkpointed(A) → client/bundle switch → joining(B) → observing(B) → reconciled(B) → active(B)`

1. quiescing：禁止新目标，撤销 lease，关闭/放弃 GUI，记录未完意图；
2. checkpointed：提交 A 的事件高水位、目标/承诺和最后观察；
3. switch：必要时重启 bundle；新 session/generation 使旧 IPC 全失效；
4. joining：按 B 的 Server Profile、身份、规则和能力连接；
5. observing：只装载 Global Self Capsule + B World Capsule，观察实际状态；
6. reconciled：与 B 的最后已知状态对账；首次进入不复制 A 资源；
7. active：同一 Persona 针对 B 当前条件自主规划。

异常断线把动作标 `unknown_after_disconnect`，不得重放。切换失败也不能虚构已经进入目标世界。

## 模型上下文

每次重大决策只组装：

1. Global Self Capsule：身份、Persona、全局偏好、知识/技能；
2. Current World Capsule：唯一当前 world/epoch/dimension、当地关系/资产/规则/目标；
3. Current Reality：本会话重新观察的状态和 capability；
4. Relevant Past：按需检索历史，每条标注来源世界和陈旧度。

其他世界库存/坐标禁止进入 Current Reality。摘要器不能去掉世界标签，也不能把“A 世界有钻石”压成“我现在有钻石”。

## 存储约束

所有世界共享同一 Kin 数据库和事件账本，不复制人格。至少需要：

- `world_context(world_context_id, server_profile_id, world_epoch, label, status, evidence)`
- `session(session_id, generation, world_context_id, bundle_id, opened_at, closed_at, close_reason)`
- `world_state_snapshot(..., freshness, payload_ref)`
- goal/plan 的 scope 字段
- `actor_identity` 与 `actor_link_evidence`
- 地点、资产、权属、承诺和事件的 world/epoch 外键

所有“当前世界”查询显式传入 world id；无作用域的地点/资产写入属于阻断。全局技能也记录适用 bundle/capability 版本。

## 必须回放

1. A 服退出再进入：人格/关系/目标连续，现实重验，旧按键不续跑；
2. A→B：B 没有 A 的家、物资、坐标和当地关系，但保留自我与通用技能；
3. A→B→A：A 计划暂停不丢，返回后先重验；
4. 同地址换档：新 epoch，旧历史可回忆但旧资产不生效；
5. LAN端口变化：配置可关联旧 world，不生成新人格；
6. 两服同名玩家：默认分开，可信关联后才共享证据；
7. 不同 bundle：旧 capability、GUI、实体和技能验证范围失效；
8. 切换中强杀：恢复后只有一个 current world，动作不重放；
9. A 的承诺到期时正在 B：可记起/计划回去，不能假装履约；
10. 模型上下文清空：恢复同一 Kin 和正确 Current World Capsule。
11. 自己建服：创建 hosted save、开放 LAN、第二客户端加入；正常/强杀重启后世界与 Kin 连续。
12. hosted→remote→hosted：全局自我连续，两边背包、地点、人物和 plan instance 不串；LAN 端口变化不改变 hosted world identity。

指标包括 `cross_world_state_leak`、`wrong_world_plan_activated`、`same_name_actor_merged_without_evidence`、`stale_session_action_replayed`、`world_epoch_mismatch`、`current_world_ambiguity`。前四项未被阻断属于严重缺陷。