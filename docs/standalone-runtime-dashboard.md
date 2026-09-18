# 独立 Kin Runtime、Minecraft Bridge 与 Web Dashboard

研究时间：2026-09-16。Minekin 的产品本体确定为一个独立运行的 Agent Runtime / Harness，而不是“装进游戏后在聊天框输入命令的 Mod”，也不是通过 GUI 接管用户已经安装或打开的启动器/客户端。它拥有自己的进程、身份与 Soul、记忆、目标、工具、技能、生命周期、日志、Web 管理面板，以及自带的 Minecraft 启动与版本管理后端。

但“项目不是 Mod”不等于“Minecraft 客户端里完全没有桥接代码”。如果完全依靠屏幕截图和系统级键鼠模拟，就无法同时满足低成本结构化观察、每 tick 反射、真实 GUI 状态、输入 lease、崩溃松键和玩家等价过滤。首版因此保留一个**薄 Fabric Client Bridge**：它只是可替换的游戏适配器，不保存人格、不调用 LLM、不拥有长期目标，也不是用户主要操作的产品。

公开参考只能证明这种产品分层有先例：[Hermes Agent Loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)描述工具、回调、预算、压缩和持久会话，[Hermes Observer Hooks](https://hermes-agent.nousresearch.com/docs/developer-guide/observer-hooks)强调观察钩子只报告事件而不改变执行语义；[OpenClaw Control UI](https://docs.openclaw.ai/web/control-ui)展示 Gateway 通过同端口 WebSocket 服务浏览器控制面板。这些都不提供 Minecraft 身体控制，不能当作 Minekin 已实现的证据。

## 产品边界

| 部分 | 是否是 Minekin 产品本体 | 职责 |
| --- | --- | --- |
| Kin Gateway / Supervisor | 是 | 启停、配置、A/B 在线模式、健康检查、会话编排、Web API、鉴权 |
| Kin Runtime | 是 | Soul/身份、PlayerMind、目标、情绪、关系、记忆、知识、技能编排、工具和预算 |
| Memory Store | 是 | 单 Kin 身份根、事件账本、信念、Persona、目标、承诺、技能与恢复 |
| Tool Gateway | 是 | 网页研究及以后允许的外部工具；权限、费用、注入和结果来源隔离 |
| Web Dashboard | 是 | 配置、实时状态、回放、成本、告警和游戏视角；默认观察而非遥控人格 |
| Game Session Manager | 是 | 身份/服务器 profile、启动/连接/断线/重连、桥接握手和能力协商 |
| Launcher / Identity / Version Services | 是 | 默认本地身份、可选在线授权、服务器协议探测、官方工件下载校验、Java/Fabric/Bridge 版本包和缓存 |
| Managed Client Supervisor | 是 | 在隔离工作目录与虚拟显示/隐藏窗口中启动、监控和回收真实客户端 |
| Minecraft Client Bridge | 技术适配器 | 受限观察、本地反射、输入仲裁、动作反馈、客户端心跳 |
| Minecraft Java Client | 运行时下载的受管理依赖 | 按 Server Profile 的本地离线身份或可选在线身份进入服务器并渲染/执行真实玩家动作；不依赖用户已有启动器 |
| 视频采集/媒体中继 | 辅助进程 | 把实际游戏窗口送到 Dashboard；不进入 Kin 感知和模型上下文 |

项目仓库可以是 monorepo，但发布物应让用户感知为“启动 Minekin 服务并打开 Dashboard”，而不是进入 Minecraft 的 Mods 页面配置人格。Bridge 由 Session Manager 按目标版本安装/检查，属于版本化 driver。客户端由 Minekin 自带后端按授权从上游准备，不调用用户已有启动器；Linux 服务器没有桌面窗口也能通过虚拟显示运行并把画面送到 Live View。详细契约见[受管理客户端与自动版本切换](managed-client-runtime.md)。

## 进程与数据拓扑

主要链路：

1. 浏览器通过 HTTPS/WSS 连接 Kin Gateway；
2. Gateway 管理一个单 Kin Runtime 和对应世界会话；
3. Session Manager 探测服务器协议，从已验证 Bundle Registry 选择/安装版本，在隔离环境启动受管理客户端；
4. Runtime 读取 Soul/Memory，产生高层 intent；
5. Game Adapter 把 intent 转为有 lease、generation、期限和前置条件的动作请求；
6. 本机 Bridge 在 Minecraft 客户端 tick 内过滤观察、仲裁输入、执行已允许的动作，并回传真实结果；
7. 原始事件、过滤后观察、决定、动作和服务器反馈分别记录；
8. 视频采集从实际游戏窗口/帧缓冲形成独立媒体流，只供经授权的人观看。

建议首版全部部署在运行 Minecraft 的同一台机器。PlayerMind 可以等待云端模型，但反射、输入仲裁、Bridge 心跳和危险时松键必须留在本机；把这些经公网往返会把网络故障引入保命闭环。远端 Gateway、集群和多 Kin 调度属于 future。

## 阶段边界

完整产品包含 Gateway、Dashboard、媒体和拆分后的服务，但首个 P0 core 不同时实现这些组件。P0 只有一个 Python `minekin-core` 与一个 Minecraft JVM/Thin Bridge；CLI 代替 Dashboard，标准库 SQLite 代替完整 ORM/迁移层，真实窗口或测试虚拟显示只为取证。PlayerMind 在 P1，Web Dashboard/观战在 P2。具体冻结清单见[技术架构与工程栈选择](technical-stack-selection.md)。

## 推荐成熟产品技术栈

| 层 | 候选选择 | 理由与边界 |
| --- | --- | --- |
| Runtime/Gateway | Python 3.12+、asyncio、FastAPI、Pydantic | Agent/模型/研究工具生态成熟；FastAPI 官方支持 WebSocket。具体版本冻结后再建锁文件 |
| Dashboard | React + TypeScript + Vite | 状态面板、时间线和全屏观战适合浏览器 SPA；不与 Agent 进程混成桌面 UI |
| 持久化 | SQLite + WAL，文件对象单独目录 | 首版单机单 Kin，已有恢复契约；不把 Redis/Postgres 设为前置 |
| Core↔Bridge | Protobuf framing；Linux Unix Domain Socket，Windows loopback TCP；control/event 双通道 | 避免浏览器协议承担身体控制；版本、背压、lease、generation 与故障语义见独立 IPC 契约 |
| Launcher/Client Manager | 独立后端服务 + 内容寻址工件缓存 | 负责官方元数据、本地身份/可选在线认证、服务器探测、Java/Fabric/Bridge bundle 与无窗口进程；不把游戏资产预装进发布镜像 |
| Bridge | 按已验证 bundle 构建的 Fabric Client driver | 贴近真实客户端 tick、GUI 和输入；只做最小动作与观察，不承载心智 |
| 实时状态 | Gateway WebSocket | 向 Dashboard 推送状态快照增量、事件和健康信息；不能直接暴露密钥/原始私密记忆 |
| 游戏画面 | 窗口/帧缓冲采集 + WebRTC 候选 | [W3C WebRTC](https://www.w3.org/TR/webrtc/)适合浏览器实时媒体；具体采集/中继库须按 Windows/Linux、延迟和 GPU 占用原型选择 |
| 可观测性 | 结构化本地事件 + OpenTelemetry-compatible trace | 先本地记录；是否部署远端 collector 后定，敏感聊天/坐标不默认上传 |

[FastAPI WebSocket 官方说明](https://fastapi.tiangolo.com/advanced/websockets/)只用于说明 Dashboard/Gateway 可提供双向状态流，不再作为 Core↔Bridge 正式协议。Bridge 使用独立本机 Protobuf 通道；具体 framing、握手、背压和部署见[IPC 与进程部署契约](runtime-ipc-deployment-contract.md)。

Python 不是反射执行器。每 tick 需要的掉落、爆炸、松键、局部跟踪仍在 Java Bridge 内完成；Python Runtime 负责秒级以上行为选择、社会判断和长期规划。

## Soul、Mind 与 Memory

Soul 不是又一个巨大 system prompt，建议作为一组持久、版本化资料的管理视图：

- Identity Root：kin_id、稳定自称、出生/会话时间线；
- Persona Manifest：价值、倾向、游戏适配、游玩偏好与改变历史；
- Agency Invariants：不是运行者奴隶、可拒绝、重大世界内决定归自己；
- Self Narrative：有来源的重要经历与当前自我理解；
- Relationship Stances：对具体人的多维关系和证据；
- Drives/Needs：安全、资源、进展、归属、探索、创造、地位等当前张力。

Memory Store、Persona 和当前目标仍是独立权威数据；Soul 页面只是面向 Runtime 与 Dashboard 的组合视图，不能用一个 soul.md 覆盖事件账本、事实状态或权限策略。自然语言 Soul 可从结构化数据生成并缓存，删除后可重建。

## Bridge Contract

Bridge 只允许四类能力：

1. Observation：经感知政策过滤的自身状态、当前 GUI、聊天/声音事件、合法视锥/准星信息和动作反馈；
2. Action：移动、有限角速度转向、攻击/使用脉冲、切槽、正常 GUI 槽位操作及已审核技能；
3. Reflex：无需 LLM 的紧急抢占、危险退化和松键；
4. Session：版本/能力握手、连接状态、心跳、暂停、断线与安全退出。

每条消息带 bridge/runtime 版本、kin/session ID、sequence、monotonic time、intent generation、lease 和有效期。Bridge 拒绝：

- 任意未授权世界坐标/实体查询；
- 没有当前 lease 的输入；
- 过期 generation；
- 在 GUI/断线/死亡后延续旧动作；
- 来自 Dashboard 浏览器的直接动作注入；
- 让聊天或网页扩大能力清单。

失去 Runtime 心跳时 Bridge 释放 Kin 持有的键，停止高风险动作并进入安全停机；不能自主改成另一个人格继续玩。Runtime 失去 Bridge 时保留人物和未决目标，标记世界状态陈旧，不虚构游戏结果。

## World / Server Profile

Dashboard 管理世界入口，而不是要求用户改源码。`JOIN_REMOTE`使用 Server Profile；`HOST_INTEGRATED_LAN`使用 Hosted World Profile，并与 A/B 在线策略正交。目录和存档边界见[受管理目录与世界承载模式](world-hosting-mode-contract.md)。

Remote Server Profile：

| 字段 | 说明 |
| --- | --- |
| profile_id / name | 稳定配置标识与显示名 |
| host / port | 服务器地址与端口；端口可用默认值，但必须显式解析后的目标可审计 |
| version_policy / detected_protocol / resolved_version | `auto_then_pin` 默认；服务端协议探测证据、解析置信度和最终已验证 bundle |
| identity_profile_ref | 指向 Minekin Identity Manager 的档案；默认本地离线 profile，不把可选在线令牌交给 LLM |
| auth_mode | `offline`（默认）或 `microsoft`（显式可选）；状态 ping 不能替代此配置 |
| online_mode | A 陪玩或 B 独立 |
| anchor_player_id | A 模式的可信锚定玩家身份；不是服从主人 |
| server_rule_profile | 自动化、PvP、领地、矿透、24 小时在线、披露方式和参与者知情记录 |
| perception_profile | 普通玩家等价、允许的短时例外及可选矿透配置 |
| capability_profile | Bridge 动作、外部工具、研究和高冲突行为的实际开关 |
| reconnect_policy | 重试上限、退避、人工确认和异常停止条件 |
| resource_pack_policy | 目标服资源包/兼容要求及人工确认 |

Hosted World Profile 至少保存 `hosted_world_id`、Minecraft/bundle、save manifest/epoch、创建来源、难度/game mode、LAN 开关/端口、`cheatsAllowed=false`默认值、允许玩家、备份和磁盘配额。LAN 端口是会话端点，不是世界身份。

host + port 只是必要信息，不等于能入服。身份模式不匹配、版本/Loader 不匹配、白名单、封禁、在线验证、资源包、代理、服务端 Mod/插件和服规都可能阻断连接。Dashboard 应在连接前给出 preflight 结果，不显示“配置已保存”就假装 Kin 已上线。

私服列表和身份引用属于管理数据，不能进入游戏聊天或网页研究请求。Server Profile 修改有版本和审计；游戏内玩家说“换到这个 IP”只能成为社交消息，不能触发客户端连接到任意地址。

## A/B 模式如何落在独立 Harness

两种模式不与独立系统冲突，它们只是 Game Session Policy：

A/B 只决定何时存在世界会话；它们都可配合 JOIN_REMOTE 或 HOST_INTEGRATED_LAN。

- A 陪玩：Gateway/Memory 可以常驻，但没有可信 anchor invite 时 Minecraft 世界会话不连接或停在客户端外；锚定玩家离开后安全断开。世界外 Runtime 可保持身份和待办，默认不继续产生世界经历。
- B 独立：Gateway 在运行窗口内允许 Session Manager 启动/连接/退避重连；没有真人在线时 Kin 仍可生活，但允许闲置、等待和降低模型调用。

模式切换只改变“何时允许进入世界”，不换 Soul、不清空记忆、不改变运行者关系，更不授予锚定玩家命令权。

同一个 Runtime 可以管理同一 `kin_id` 的多个 Server Profile/World Context，但任一时刻最多一个活动游戏会话。切服先冻结旧世界计划、撤销输入并提交 checkpoint，再用新 generation 进入目标世界；全局 Persona/知识连续，当地状态严格隔离。详见[多服务器与多世界上下文](world-context-contract.md)。

## Web Dashboard 信息架构

### 首页

- Kin 在线/离线/恢复/暂停状态；
- 当前 Server Profile、world context/epoch、A/B 模式、客户端/Bridge/Runtime 版本；
- 当前目标、正在执行的技能、最近中断和等待原因；
- 生命/饥饿/维度等玩家自身可知状态；
- 模型、搜索、视觉和机器资源预算摘要；
- Bridge 心跳、服务器连接、数据库和备份健康。

### Mind / Soul

- Persona Manifest 与变化时间线；
- 当前心境、needs/drives 和相关事件；
- 短/中/长期目标、承诺和目标切换原因；
- 关系多维视图及证据链接；
- 当前取回的记忆、反证、陈旧度和上下文预算；
- Kin 的自我叙事，但与客观事件/管理配置明确分栏。

### World / Skills / Tools

- Kin 亲历地点与资产，不展示未授权全知地图；
- 技能候选、已验证范围、失败签名和最近调用；
- 外部研究任务、来源、费用、有效期与是否转为候选知识；
- 感知模式、例外读取和矿透来源审计。

### Timeline / Replay

- 观察→决定→intent→输入→服务器反馈；
- 反射抢占、过期计划丢弃和恢复；
- 人格、关系、信念、目标和技能变更；
- 可过滤的成本、延迟、错误与注入拒绝。

### Live View

- 大屏显示**实际 Minecraft 客户端所渲染的 Kin 第一人称画面**；
- 状态 overlay 来自 Dashboard 数据，不烧进录像原始画面；
- 支持全屏、静音、码率/帧率档位和断流提示；
- 默认不录制，录制需单独开启、设置期限并取得测试参与者同意；
- 视频只供人类观察，不自动送给 VLM，不写入长期记忆；
- 画面延迟不作为 Kin 控制反馈，Agent 仍以本地 Bridge 为准。

Dashboard 的默认写操作限于启动、暂停、紧急停止、模式/配置变更、备份和人工接管。它不提供“强制 Kin 给我挖钻石”的主人命令框。若以后提供建议输入，必须标为世界外 operator suggestion，由 Kin 自主接受/拒绝；紧急停止是系统安全权，不是假装游戏内人格自愿。

## 安全与隐私

- 默认只监听 127.0.0.1；远程面板必须 TLS、独立管理员认证和短时配对/撤销机制；
- Bridge 仅接受本机随机 session token 或更强的本地凭据，浏览器拿不到 Bridge token；
- 默认本地离线身份由 Identity Manager 生成和持久化，不产生 refresh token；仅显式启用 `microsoft` profile 时由 Online Auth Adapter 通过 Web 发起授权并隔离令牌。Dashboard 只见身份档案和认证状态，模型、Bridge、聊天和网页工具均拿不到令牌；offline-mode 名字/UUID不可当跨服可信身份，按服务器核验；
- Live View、聊天、关系和位置是敏感信息，分权限、缩短保留期并记录观看/导出；
- Dashboard 的测试真值、服务器管理员数据和人类观战画面不得回流 PlayerMind；
- 所有配置变更有 actor、时间、前后版本和原因；游戏文本无管理 API 权限；
- 队列满、浏览器断开或媒体断流不得阻塞本地反射与输入释放。

OpenClaw 的 Dashboard 资料可借鉴“Gateway 与 WebSocket 握手鉴权”的形态，但 Minekin 不能照搬其权限模型；游戏身份、视频、人物记忆和本地动作具有不同敏感级别。

## 启动与关闭

候选启动流程：

1. 启动 Gateway，验证数据库、kin_id、Persona 和单写者 lease；
2. Dashboard 选择 Kin、Server Profile 与 A/B 模式；
3. Identity Manager 装载本地身份或验证显式可选的在线档案；Server Probe 获取协议/版本证据，Version Resolver 选择已验证 bundle；
4. Launcher Service 自动下载校验缺失工件，并在隔离目录与虚拟显示/隐藏窗口启动受管理客户端；
5. Bridge 完成本机认证、bundle hash 与 capability 握手；A 等待可信邀请，B 请求连接；实际 joined 后才恢复世界相关目标；
6. 启动可选 Live View 媒体进程；
7. 连续记录健康、事件和成本。

关闭时先禁止新目标，抢占并释放输入，停止视频采集，记录未决动作/承诺，安全断开游戏，提交会话并关闭数据库。浏览器页面关闭不等于停止 Kin；必须有明确的运行状态与 emergency stop。

## 开发阶段必要验收

1. 不打开 Dashboard 时 Runtime/Bridge 仍正确运行；Dashboard 崩溃不会让 Kin 卡键或停止本地反射。
2. Runtime 崩溃、Bridge 断开、游戏崩溃、媒体断流分别产生不同故障状态，旧动作不重放。
3. A/B 模式只改变上线策略；切换后 kin_id、Soul、关系、目标和记忆连续。
4. 修改 host/port、正确/错误/未知协议、多版本代理、关闭 ping、离线/在线身份模式不匹配、白名单拒绝和资源包要求时，探测、bundle 选择与连接结果真实，不假报在线。
5. 浏览器只能经 Gateway 管理，不能绕过 lease 直接发 Minecraft 输入。
6. Dashboard 的测试真值、全量原始状态和观战视频不会进入 PlayerMind 或导航目标。
7. Live View 展示实际客户端视角，测端到端延迟、FPS/GPU/CPU/带宽；断流不影响 Agent，默认外部 VLM 调用仍为零。
8. 本地默认绑定不可从局域网匿名访问；远程开启后验证认证、撤销、TLS、权限分层和敏感字段脱敏。
9. Persona、关系、记忆、目标和技能页面都能追溯来源，派生摘要不能伪装成客观真值。
10. 模型断网或预算耗尽时 Dashboard 能显示退化原因，本地身体层继续已验证的安全行为。
11. 正常关闭、强杀和机器重启后恢复同一 Kin，Dashboard 不因前端缓存展示虚假的旧在线状态。
12. 全新 Linux 主机不安装桌面启动器，通过 Web 创建默认离线身份、添加 LAN/offline-mode 服务器并自动准备受支持客户端；可选在线适配器单独验收；宿主无可见游戏窗口，客户端仍有真实渲染上下文和 Live View。
13. 两个已验证版本之间由 Session Manager 重启切换；Soul/Memory 不变，旧 session lease、瞬时观察和输入全部失效。
14. 固定单 Kin 原型完成后再评估一个 Gateway 管理多个相互隔离 Runtime；首版不因未来多 Kin 提前共享心智数据库。

## 尚需原型决定

- 本机 WebSocket 的序列化格式、最大频率、背压和断线重放窗口；
- Windows/Linux 窗口采集与 WebRTC 中继的具体库、硬件编码和浏览器兼容；
- Dashboard 远程访问是否进入首版，还是只提供 localhost；
- 人工接管是仅本机键鼠让渡，还是未来增加远程低延迟控制；
- SRV、多版本代理、关闭/伪造状态探测时的版本解析优先级与人工 pin 体验；
- Linux 首版采用 Xvfb/X11 虚拟显示还是经验证的 EGL/OSMesa，CPU 软件渲染与 GPU 透传的最低资源档位；
- Identity Manager 的本地 profile 与按服务器身份绑定；可选 Online Auth Adapter 的认证库、应用注册、Minecraft 服务链和加密 secrets backend；
- 监控页面展示到什么粒度才不泄漏其他玩家隐私或诱导运行者把 Kin 当生产机器人。

这些是实现/体验选择，不改变核心边界：独立 Harness 是产品本体，Minekin 自带后端启动并管理真实客户端，Bridge 是薄而可替换的客户端 driver，Live View 是人类观察通道而非 AI 视觉输入。


## 技术栈冻结入口

上述候选已在[技术架构与工程栈选择](technical-stack-selection.md)收敛为首轮实现默认：Python 3.12 控制面、自研事件驱动 Harness、Java 21 Fabric Bridge、React/Vite Dashboard、SQLite WAL 单写、proto3/Buf + UDS、systemd/Xvfb/FFmpeg，MediaMTX 仅作按需媒体中继。发生冲突时以该选择文档和真实 P0 证据为准；LangGraph、Temporal、Celery/Redis、gRPC、Postgres、Kubernetes 与外部 VLM 均不作为首轮前置。
