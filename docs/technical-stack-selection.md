# 技术架构与工程栈选择

核对时间：2026-09-17。本文把已有产品设计收敛为首轮可实现、可替换、可取证的工程栈。它是实现默认值，不是“所有候选都要安装”的采购清单；若真实原型推翻假设，按证据修订。

## 结论

Minekin 的目标形态采用**单机优先、可拆分的模块化单体**，而不是聊天机器人框架、Minecraft 协议 Bot、桌面 GUI 自动化或一开始就做微服务。这里必须区分“最终产品边界”和“P0 实际开工形态”：P0 只运行两个主要进程，不按最终拓扑一次性拆服务：

- Python 控制面承载 PlayerMind、持久状态、工具、模型编排、会话和 Dashboard API；
- Java 21 Fabric Bridge 驻留于 Minekin 自己启动的真实 Minecraft 客户端，只负责 tick 级观察、反射、输入仲裁和动作反馈；
- React Web Dashboard 只观察和管理，不直接向 Bridge 注入动作；
- SQLite 保存单 Kin 的身份、事件、关系、目标、技能与作业；文件对象和证据包单独保存；
- Protobuf 作为 Python↔Java 的版本化契约；Linux 用 Unix Domain Socket，Windows 开发档用 loopback TCP；
- Linux 首发用 systemd/cgroup v2、Xvfb 和 FFmpeg；容器是后续交付方式，不是 P0 前置；
- Agent Harness 自研，通用 Agent 框架只允许作为局部适配器，不能拥有 Soul、Memory、权限或身体控制权。

这套方案保留“独立大型 Agent 系统”的产品形态，同时承认真客户端需要一个薄 Bridge。Python 从不进入逐 tick 保命闭环，Java Bridge 也不拥有 Kin 的人格。

## 分阶段技术栈：防止一次造完

| 阶段 | 只引入什么 | 明确不做 | 退出条件 |
| --- | --- | --- | --- |
| P0 Core | Python 3.12 + `asyncio` + 标准库 `sqlite3` + CLI；Java 21 + Fabric；proto3 + 本机 socket；pytest/JUnit | FastAPI、React、Node、SQLAlchemy/Alembic、模型、PlayerMind、Baritone、视频、容器、OpenTelemetry | 真客户端启动、离线服 JOIN、首快照、短 lease 输入、松键与强杀恢复都有证据 |
| P1 PlayerMind | Pydantic、`httpx`、模型适配、目标/关系/记忆/技能状态机、受限 Tool Gateway；按数据迁移需要再引入 SQLAlchemy/Alembic | 漂亮 Dashboard、实时视频、多模型路由、MCP 市场、分布式作业 | 单 Kin 能持续游戏日、拒绝/改目标、跨重启保持同一人格和世界隔离 |
| P2 产品化 | FastAPI/Uvicorn、React/TypeScript/Vite、Dashboard、Xvfb/FFmpeg、正式迁移与备份、结构化 telemetry | Kubernetes、多主机、多 Kin 集群 | 可配置、可观战、可回放、可升级并满足单机长期运行 |
| Future | MediaMTX/WebRTC、MCP 连接器、Postgres、Temporal、OCI、多 Kin 调度 | 没有测量依据就提前引入 | 仅由升级触发条件启动专题原型 |

P0 的依赖清单应短到可以一次看完：`Python + Java/Fabric + Protobuf/socket + SQLite + CLI + 测试`。表中后续组件只是架构预留，不得出现在 P0 的“必须安装/必须掌握”列表里。

### P0 只有两个主要进程

```text
minekin-core (Python)
├── launcher
├── session runtime
├── SQLite event ledger
├── CLI
└── test/evidence hooks

Minecraft JVM
└── Fabric Thin Bridge
```

受控原版服务器和 test-orchestrator 是测试夹具，不算产品常驻服务。P0 不独立启动 Gateway、Launcher、Runtime、媒体服务和 Dashboard；Python 包内保留模块边界，以后按故障隔离和安全需要拆进程。即使暂时同进程，仍禁止浏览器直达 Bridge、绕过 lease 或让 Launcher 修改人格数据。

## 目标产品进程拓扑（P2 以后）

| 进程 | 首选实现 | 唯一权威/边界 |
| --- | --- | --- |
| `minekin-gateway` | Python、FastAPI、Uvicorn、Pydantic v2 | 配置/API/WSS/鉴权；不直接写 Bridge、不读取数据库文件 |
| `minekin-runtime` | Python 3.12、asyncio、Pydantic v2 | PlayerMind、调度、模型、工具、唯一数据库写者、会话恢复 |
| `minekin-launcher` | Python 3.12、httpx、内容寻址缓存、子进程监督 | 版本解析、工件校验、独立 run directory、客户端生命周期；不修改 Soul |
| Minecraft JVM + Bridge | Java 21、Fabric Loader/API、Gradle/Loom | 合法客户端事件/输入、反射、动作回执；不调用 LLM、不写长期记忆 |
| `minekin-media` | Xvfb + FFmpeg；MediaMTX 为可选中继 | 真实客户端画面采集；断流不影响 Runtime，不进入默认模型输入 |
| Dashboard | React + TypeScript + Vite | 人类观测、配置、回放、急停；浏览器永不持有 Bridge 凭据 |

这些是成熟产品的权限边界，不是 P0 同时开工的进程清单。P2 以后才根据故障隔离与远程管理需要拆出独立入口；P0 始终只有 `minekin-core` 与 Minecraft JVM 两个主要进程。P0 不引入 Kubernetes、服务网格、Kafka、Redis、RabbitMQ 或分布式数据库。

## Agent Harness：自研事件驱动内核

核心不用 LangChain、LangGraph、CrewAI、AutoGen 或 OpenClaw/Hermes 直接充当 Runtime。Minekin 需要的不是“模型连续调用工具”，而是四种不同时间尺度、可抢占的控制：

1. Bridge tick loop：本地反射、松键、局部动作跟踪；
2. Runtime executive loop：事件归并、意图前置条件、技能状态机、中断/恢复；
3. deliberation loop：秒级行为选择、社交判断、目标重排；
4. consolidation loop：记忆晋级、反思、技能候选、长期规划。

Python 内核采用 `asyncio.TaskGroup` 做结构化并发；每个会话有 supervisor、有限队列、deadline、generation 与取消树。事件先写入持久账本，再由纯 reducer 形成 belief/current view；LLM 输出只能产生带 schema 的 proposal，必须经过 policy、现实前置条件和能力检查才能变成 intent。模型超时不会阻塞 Bridge。

### 内部接口

首版固定以下协议面：

- `ModelProvider`：聊天/结构化输出/流式响应/用量；供应商适配器在边缘；
- `MemoryRepository`：确定性身份包、结构化查询、FTS、可追溯摘要；
- `ToolProvider`：公开资料查询、期限、预算、来源与失败类型；
- `GameAdapter`：观察、intent、lease、取消、动作结果；
- `SkillExecutor`：显式 SkillSpec 状态机，不能执行任意生成脚本；
- `PolicyEngine`：能力、世界/服务器规则、感知例外、出站泄漏检查；
- `EvidenceSink`：三时间线、trace、截图/录像引用和验收结果。

OpenAI-compatible API 可以作为模型适配面的一个实现，但不把任何单一模型厂商 SDK 扩散到领域层。首版优先用 `httpx` 写薄适配器；只有实际需要大量供应商路由后，才评估 LiteLLM 等代理层。

### 为什么不把通用 Agent 框架放在核心

| 候选 | 决策 | 原因 |
| --- | --- | --- |
| LangGraph | 不作核心；以后可用于隔离的研究/规划子图 | 它的持久图适合可重放工作流，但 Minekin 的身体抢占、世界 freshness、输入 lease 与人格账本必须由领域内核定义 |
| Temporal | P0 不引入 | 适合跨服务耐久工作流，不适合 tick/秒级身体闭环；单机单 Kin 为此运行服务端得不偿失 |
| Celery/Redis | P0 不引入 | 外部查询作业量低，SQLite 作业表 + asyncio worker 已能持久恢复 |
| CrewAI/AutoGen | 不采用 | 当前重点是一个 Kin；多 Agent 对话抽象不能替代独立身体和世界隔离 |
| Hermes/OpenClaw | 借鉴，不依赖其核心 | 借鉴 session、skills、tool gateway、observer/dashboard；不继承其权限模型或 Minecraft 能力 |
| MCP | 外部工具可选适配器 | MCP 是能力接入协议，不是信任边界；每个调用仍需 Minekin policy、预算、schema 与出站检查 |

## 语言与依赖基线

### Python 控制面

- Python `3.12.x` 作为 P0 基线；项目声明 `>=3.12,<3.14`，验证后再扩大；
- P0 用 `uv` 单项目锁文件、标准库 `asyncio/sqlite3`、生成的 Protobuf 类型、Ruff、Pyright、pytest；
- P1 才加入 Pydantic v2 与 `httpx`，用于领域 schema、模型和公开资料适配；
- SQLAlchemy 2.x + Alembic 仅在表结构和迁移复杂度证明需要时进入 P1/P2；此前单写 repository 隔离 SQL，禁止业务层散写；
- FastAPI + Uvicorn、pytest-asyncio/Hypothesis 与 OpenTelemetry 在对应 API、并发属性测试和可观测需求出现时加入，不作为 W00 安装前置。

Python 3.12 是稳定工程基线而非性能层。若 profiling 证明调度或媒体路径 CPU 不足，优先隔离热点，不提前把整个控制面改写为 Rust/Go。

### Minecraft Bridge

- Java 21；
- Fabric Loader/Fabric API/Yarn 按 tested bundle 固定；
- Gradle Wrapper + Fabric Loom，启用依赖锁与校验；
- JUnit 5 做纯逻辑/协议测试，真实 `runClient` 与受控服务器做集成验收；
- Bridge 使用 Minecraft 客户端线程安全入口；I/O 和编码不得阻塞 render/client tick；
- Baritone 只作为经审计、可替换的导航候选；P0 core bundle 在没有 Baritone 时也必须能启动、握手、观察、松键和执行最小输入。

Bridge 首选 Java 而不是 Kotlin，以减少 Mixin/Yarn/Fabric 版本调试变量。以后可在非 mixin 的纯工具模块使用 Kotlin，但不是默认。

### Web Dashboard

- Node.js 24 LTS、pnpm、TypeScript strict；
- React + Vite；
- TanStack Query 管 REST server state；实时快照/事件用原生 WebSocket 客户端和小型领域 store；
- OpenAPI 生成只读/管理 API 客户端；Bridge proto 不生成到浏览器；
- Playwright 做关键流程，Vitest 做组件/纯逻辑；
- 第一版 CSS 采用轻量 token + CSS Modules，不为面板引入重型设计系统。

Dashboard 不做 SSR，不需要 Next.js。它是本地/私有控制台，SPA 静态文件由 Gateway 或反向代理提供即可。

## 持久化与记忆

### SQLite 决策

P0 用 Python 标准库 `sqlite3` 驱动本机 SQLite WAL，通过单一 repository/写队列访问；不为了 ORM 先引入 SQLAlchemy。P1/P2 出现多表迁移和管理 API 后再评估 SQLAlchemy/Alembic。选择 SQLite 的原因是单 Kin、单主机、Runtime 单写，能提供事务、恢复、备份和足够的查询能力。具体约束：

- 只有 Runtime 写数据库；Gateway/Dashboard 经 API 读取，禁止直接开写连接；
- P0 schema 使用显式版本表和受测 SQL migration；若进入 SQLAlchemy/Alembic，迁移仍必须可备份、可回滚或明确只前进；
- 开启 foreign keys、busy timeout，定义 checkpoint/备份窗口；
- SQLite 必须在启动时报告实际运行库版本；WAL 环境要求 `>=3.51.3`，或官方列明已回补的 `3.50.7/3.44.6`，否则拒绝多连接 WAL 配置；
- 数据库与 WAL/SHM 位于本地文件系统，不放 NFS/共享卷；
- 原始媒体、日志包和大型 evidence object 放内容寻址对象目录，数据库只存 hash、元数据和引用；
- FTS5 是默认文本检索；中文分词与别名由应用层索引字段补充；
- embedding 是可选派生索引，可删除重建，不成为事实权威；
- 不引入独立 vector DB、Redis 或 Postgres，直到并发 Kin、跨主机或测量数据证明需要。

### 事件模型

权威层次为：append-only domain event → 当前结构化投影 → 带引用的摘要/叙事 → 可重建索引。persona、关系、目标和技能都有版本、来源与 world context。重启从 identity root、manifest、未完成目标和最后稳定水位恢复；位置、GUI、背包、实体与旧 intent 必须重新从客户端验证。

## IPC 与 API

### Runtime↔Bridge

- `proto3` 定义 handshake、capability、observation、intent、action result、cancel、heartbeat 和 fault；
- Buf 做 lint、代码生成和 breaking-change 检查；
- 传输使用 `uint32 length + protobuf envelope`；
- Linux 为两个独立 UDS：control 与 event；Windows 开发档使用仅绑定 loopback 的 TCP；
- 每条消息含 schema version、kin/session/world、sequence、monotonic time、generation、lease、deadline；
- 不在 P0 使用 gRPC/Netty，以避免把额外线程、HTTP/2 和依赖树塞进 Minecraft JVM；
- 队列有界：状态可合并，关键事件/回执不可静默丢弃，背压升级为降级或停机。

### Dashboard

REST 用于配置、查询、动作申请和审计；WSS 用于状态增量、事件、日志尾部和告警。视频走独立媒体通道，不能把视频帧塞进 WebSocket JSON。远程访问必须由 TLS 反向代理、明确用户鉴权和 CSRF/origin 策略保护；默认只监听本机。

## Launcher、图形与媒体

Launcher 先用 Python 实现：它是元数据解析、下载校验、bundle 选择和子进程监督器，不是高频数据面。每个实例拥有独立 `run/`、`game/`、`assets/`、`libraries/`、`natives/`、`mods/`、日志与世界目录，不接触用户现有 `.minecraft`。

Linux P0 采用原生 systemd 单元和 cgroup v2：

- Xvfb 提供真实 X11 显示；Minecraft 仍正常渲染；
- FFmpeg `x11grab` 做观战采集；
- MediaMTX 仅在需要浏览器 WebRTC/LL-HLS 时作为独立 MIT 中继加入；
- 无观战者时允许停编码，Bridge 结构化观察仍运行；
- GPU/EGL/容器化是后续优化，不能在 P0 同时引入。

首发不选 Docker/Kubernetes，原因是 OpenGL/X11/GPU、cgroup、文件权限和调试证据在宿主机更直接。垂直切片通过后再提供 OCI 镜像；容器不能改变“每个实例独立目录、单写锁和本地反射”的契约。

## 外部工具与知识查询

Tool Gateway 是 Runtime 内的受限子系统，不是能任意执行 shell 的“万能工具”：

- 搜索、网页读取、下载和未来 MCP 连接器均注册 typed capability；
- URL 解析后做 scheme/host/IP 检查，阻断 loopback、link-local、内网和重绑定；目标服地址不自动成为网页白名单；
- 每个 job 有 world/context、发起原因、期限、token/金额/网络预算和 cancel；
- 网页文本进入 `untrusted_content`，只能形成带来源的候选知识；
- 生成 SkillSpec 先进入 candidate，经过静态校验、沙箱/受控世界试做和证据门禁才可复用；
- P0 禁止模型生成并直接运行 Python、Java、shell 或任意 Fabric 代码。

公开资料任务用 SQLite job/outbox 表持久化。断网时 Kin 可以承认“暂时查不到”，继续本地生存；工具恢复后不自动执行已经过期的承诺。

## 可观测性与测试

需要同时保留三条时间线：客户端单调 tick/输入、Runtime 事件/决策、外部模型/工具。OpenTelemetry trace 用于关联，领域 evidence 包才是验收权威。

测试栈：

- Python：pytest、pytest-asyncio、Hypothesis；
- Java：JUnit 5、协议 golden tests、受控 Minecraft/Fabric 集成场景；
- Web：Vitest、Testing Library、Playwright；
- Contract：Buf lint/breaking、OpenAPI schema diff、固定事件回放；
- 故障：kill -9、断 IPC、断模型、磁盘满、WAL 恢复、Bridge 卡顿、客户端崩溃、版本不匹配；
- 安全：提示词注入、SSRF、工具越权、日志泄漏、浏览器直连 Bridge、旧 generation 重放；
- 性能：tick 占用、触发到首次输入、队列深度、模型延迟/成本、数据库尾延迟、视频编码 CPU/GPU。

GitHub Actions 跑静态检查、单元、schema breaking 和 dashboard e2e。完整 Minecraft 资产/图形/服务器矩阵放手动或受控 runner，不在普通 CI 假装完成。

## Monorepo 建议布局

```text
apps/
  gateway/          # FastAPI/WSS/API
  runtime/          # Harness, PlayerMind, scheduler
  launcher/         # bundle, identity, process supervisor
  dashboard/        # React/Vite
packages/
  domain/           # Python 领域模型与 reducer
  persistence/      # SQLAlchemy/Alembic
  model_adapters/   # provider edge
  tool_gateway/     # typed tools/policy
bridge/             # Java 21 Fabric thin bridge
proto/              # proto3 + buf
ops/
  systemd/
  xvfb/
  mediamtx/
tests/
  replay/
  integration/
  fixtures/
docs/
```

P0 不创建三个 Python app：先以一个 `minekin-core` 包含 launcher/session/runtime/CLI，并以清楚模块接口隔离。P2 引入 Dashboard、远程 API 或独立权限域后，再拆为多个入口；拆分前后数据库单写、持久事件、Bridge lease 和故障恢复语义必须一致。

## 首个实现切片

按已有 W00–W70 计划，不先做完整人格或漂亮 Dashboard：

1. 冻结 P0 最小工具链与依赖上限，生成一页可审计安装清单；
2. Launcher dry-run 生成 1.21.4 offline 参数与独立目录；
3. Java Bridge 只读握手、心跳、能力与安全松键；
4. Runtime 接收受限自身快照并写入事件账本；
5. Gateway 暴露健康、会话与只读状态，Dashboard 显示连接/世界/最近事件；
6. 加一个短 lease 的“向前移动/释放”动作；
7. 强杀 Runtime/Bridge/客户端并证明无残留输入、同一 Kin 恢复且瞬时世界状态重验；
8. 以上通过后才加入 Baritone 导航、GUI、PlayerMind、模型、工具和视频。

## 升级触发条件

| 当前选择 | 只有出现以下证据才升级 |
| --- | --- |
| SQLite→Postgres | 多 Kin/多主机、单写吞吐或备份恢复实测不满足 SLO |
| asyncio jobs→Temporal/Celery | 大量跨日外部作业、独立 worker、重试/编排复杂度超过本地 outbox |
| 自研 harness→引入 LangGraph 子图 | 某个隔离规划流程确实需要图式 checkpoint/人工中断，且不触及身体和权威记忆 |
| UDS framing→gRPC | 多语言服务数量、跨主机调用、流控与工具链收益超过 JVM/依赖成本 |
| Python Launcher→Rust/Go | 校验/解压/监督的性能、安全隔离或单文件交付有测量依据 |
| 宿主机→OCI/Kubernetes | 多实例调度成为现实需求，且 GPU/显示/存储/证据链已有容器原型 |
| FTS5→向量服务 | 长期语义召回基准证明本地混合检索不足，且成本/隐私可接受 |

## 证据与局限

Python TaskGroup 提供结构化并发和取消语义；FastAPI 官方支持 WebSocket；SQLAlchemy 提供 asyncio 接口，Alembic 管理迁移；SQLite WAL 支持同机并发读和单写，但官方明确不适合网络文件系统且 2026 年披露了需升级规避的 WAL-reset bug；Protobuf/Buf 支持跨语言 schema 与兼容性检查；MediaMTX/FFmpeg 可作为媒体链候选。这些资料只支持技术选择，不证明 Minekin 已经启动、入服、保命、通关或长期不失忆。所有运行能力仍以 P0 证据包为准。
