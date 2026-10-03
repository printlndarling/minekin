# S3 最小 PlayerMind：模型接入、决策闭环与可声明范围

本文件是 S3 的协调契约，供模型适配、心智调度和后台投影三块工作并行实施时共同遵守。
它细化[自主目标调度契约](autonomous-goal-scheduler.md)的五种对象与低频闭环，并把
[s2-world-observation-and-actions.md](s2-world-observation-and-actions.md) §4 的结果核对
接成目标完成条件。本文件不新增游戏动作，也不改变已有产品契约。

## 1. 模型提供方配置与密钥隔离

配置读取沿用 `config.py` 的既有风格：环境变量注入、可传入 `Mapping` 以便测试、缺失即
具名拒止、绝不写盘也绝不创建目录。

| 变量 | 含义 | 缺失时 |
| --- | --- | --- |
| `MINEKIN_MODEL_PROVIDER` | `off`（默认）或 `openai_compatible` | 按 `off` 处理，不报错 |
| `MINEKIN_MODEL_BASE_URL` | 提供方根地址 | `MODEL_NOT_CONFIGURED` |
| `MINEKIN_MODEL` | 模型名 | `MODEL_NOT_CONFIGURED` |
| `MINEKIN_MODEL_API_KEY_ENV` | **保存密钥的变量名**，不是密钥本身 | 无鉴权端点时允许为空 |
| `MINEKIN_MODEL_TIMEOUT_MS` | 单次调用上限 | 取常量默认 |
| `MINEKIN_MODEL_RUN_COST_CAP` | 本次运行的花费上限 | 取常量默认 |

- 密钥只在发出请求的那一刻读取。Core 不持久化它，`MinekinError` 的消息、日志、run 目录
  与任何 `dataclass` 的 `repr()` 都不得出现密钥或其片段；结构化响应日志只记录提供方
  返回的用量字段。
- `MINEKIN_MODEL_PROVIDER=off` 是产品能力而不是占位开关：本地反射、已批准技能与保守
  动作照常运行，任何需要模型输出的调用点都返回具名拒止 `MODEL_NOT_CONFIGURED`。
- 提供方只允许在编排方显式配置时访问网络；离线受控镜像与 CI 永不触达真实端点。

## 2. 模型端口只提出判断，不签发按键

`ModelProvider.decide(request) -> Decision | ModelUnavailable`，请求带当前观察摘要、
需求、活跃目标、**本地层已经算出的可行技能集合**、人格种子与预算余量；响应是受结构
校验的意图，而不是自由文本。

- 模型只能在可行集合内选择，不能引用未提供的物品、坐标、技能或"已观察到"的事实；越界
  即 `DECISION_OUT_OF_BOUNDS` 拒收。
- 每个决定带 `intent_generation`。generation 不匹配的迟到返回直接丢弃，不得把已取消的
  意图重新写回按键。
- 超时、结构不合规与 `ModelUnavailable` 都走同一条保守路径：保留原事件与原目标，不伪造
  记忆，也不自动扩大重试预算。

## 3. 目标、需求与失败归因的最小实现

S3 只做调度契约五种对象中的两样：**当前意图**与一项**长期方向**（默认取"取得并留住基础
工具"这一可观察里程碑）。承诺与关系留待 S5，不在本阶段留半成品字段。

- 需求只实现可从玩家等价观察直接推出的两项：`resource_security`（背包里有没有木制工具）
  与 `safety`（生命值/饥饿值读数）。数值是排序用的内部变量，不生成台词。
- 稳定初始人格由 `kin_id` + 人格种子派生并持久化，重启后读回同一份；人格版本与派生算法
  一起记录，绝不在每次入服时重新随机。
- 人格的这一版已落地：`domain/persona.py` 用 `persona-blake2b-v1` 从 `(kin_id, seed)` 派生
  五项 1..9 的广义倾向和六项价值的排序，`adapters/filestore/persona_store.py` 把它写成 Kin
  根目录下的 `persona.json`——文件已存在即拒写（`PERSONA_ALREADY_INITIALISED`），缺失即具名
  报出（`PERSONA_NOT_INITIALISED`），不给读的人编一个人。种子取自 `MINEKIN_PERSONA_SEED`；
  未设置时 `init` 抽取一次并连同人格持久化，因此这个 Kin 是谁事后仍可由它自己的目录复现。
  `minekin persona show` 只读回人格与算法/版本，不回显种子。人格没有进 SQLite，`schema.sql`
  与迁移的冻结摘要因此不变。
  2026-10-03：决策接口现在可携带已保存的 Manifest，把五项倾向、价值排序、版本与
  `manifest_sha256` 作为受约束输入传给模型，并写入心智运行记录；不外发原始 seed。
  缺失 Manifest 明确为未知，其他 Kin 的 Manifest 在建心智时拒绝。启动模块已从
  当前 Kin 目录读取同一 Manifest，环境 seed 改变不会重抽，损坏文件不静默回退。
  读盘/重启与模型请求已用本地回归及假端点验证；**尚未证明真实 LLM 在游戏里表现出
  不同人格**。人格不扩张可行动作或权限，也不映射为固定脚本。
- 失败归因先实现四类真实可判的：`RESOURCE_UNAVAILABLE`、`SKILL_NOT_IMPLEMENTED`、
  `ACTION_NOT_EFFECTIVE`、`INSUFFICIENT_INFORMATION`。同一失败上下文签名耗尽重试预算后
  必须换方法、等待或放弃，不得原样重放。
- 目标完成条件只能由 S2 §4 的服务端同步结果满足；模型或技能自报"完成"不关闭目标。

## 4. 成本账本

`domain/budget.py` 记的是时延分位，不能复用为花费账本，因此新增按调用聚合的记录：
提供方、模型名、请求/响应量、估算花费、发起时的意图 generation、结果（成功/超时/拒收）。
账本支持只读投影到后台，并支持 `MINEKIN_MODEL_RUN_COST_CAP` 在超限后拒绝再发起调用——
超限是停止调用，不是停止游玩。

## 5. 后台只读投影

后台需要能解释一次自主运行，字段限定为：当前长期方向、当前意图与其理由、发起意图时依据
的观察、正在执行的技能与最近一次真实结果、失败归因、模型调用次数与花费、以及**模型是否
启用；未启用时给出 `MODEL_NOT_CONFIGURED` 这类真实原因**。任一格没有真实来源就显示为空
并说明原因，不以占位值填满。

## 6. 验收与可声明范围

- 单元与受控会话验收：提供方契约用本地假 HTTP 端点覆盖（正常、超时、结构不合规、越界
  选择、`off` 模式五类），不依赖任何真实凭据；密钥隔离用"把假密钥放进环境后 grep 全量
  日志与 run 目录"证明。
- **可以声明**：结构化决策端口、超时与过期丢弃、本地前提校验、真实结果核对、失败改线、
  成本限额与后台解释，在无模型模式和对着本地假端点两种形状下均成立。
- **不可声明**：在没有真实模型凭据的机器上，"由大模型自主选定目标并完成"不属于已验证
  能力；假端点返回的动作序列是测试夹具，不是自主性证据。缺失哪一项凭据要在交付说明里
  点名，而不是用确定性规划器的成功替代。
