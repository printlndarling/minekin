# Runtime、Bridge IPC 与单机进程部署契约

研究时间：2026-09-16。本文件把“独立 Agent Harness + 薄 Fabric Bridge”落实为首个原型可实现的进程、传输、消息与故障边界。以下是设计决策和待测指标，不是已运行结果。

## 首版技术决定

| 项目 | 首版决定 | 不采用/延期 |
| --- | --- | --- |
| 部署 | 单机、单 Kin、分进程；反射与输入仲裁在 Minecraft JVM 内 | 公网控制回路、多机调度 |
| Bridge 传输 | Linux Unix Domain Socket；Windows 开发档回退随机 loopback TCP | 浏览器直连 Bridge |
| 编码 | 长度前缀 Protobuf envelope；脱敏 JSON 只作调试视图 | 让 JSON 字段漂移充当正式协议 |
| 通道 | control 与 event 两条独立连接和有界队列 | 视频/日志/控制共用无界队列 |
| Web | FastAPI/HTTPS/WSS 只服务 Dashboard/管理 API | 用 Dashboard WebSocket 承担 tick 控制 |
| 监督 | P0 用 systemd 服务/作用域与 cgroup v2；闭环后再做 OCI profile | 同时调试容器、GPU、动作和全 Agent |
| 数据 | Runtime 是 SQLite 单写者；Bridge 不写人物库 | Bridge/Dashboard/模型并发改 Soul |

Java 21 的 [UnixDomainSocketAddress](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/net/UnixDomainSocketAddress.html) 与 [SocketChannel](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/nio/channels/SocketChannel.html)提供 Unix-domain socket 原语；Python 3.12 [asyncio streams](https://docs.python.org/3.12/library/asyncio-stream.html#asyncio.start_unix_server)提供 Unix 异步流。它们不证明 Minekin 的延迟和恢复已经通过测试。Windows 不承诺 Unix socket，使用仅绑定 `127.0.0.1` 的随机端口和同一应用协议。

Bridge 选 JDK NIO + Protobuf framing，而不是嵌入 gRPC/Netty，以减少 Minecraft/Fabric JVM 的 HTTP/2、Netty 与传递依赖冲突面。这是待验证的工程取舍；若自写 framing 原型维护性差，再用实测结果重评。

## 进程与所有权

| 进程 | 拥有 | 禁止拥有 |
| --- | --- | --- |
| `minekin-gateway` | Dashboard API、管理员鉴权、配置审计、Supervisor 状态 | Bridge token、直接游戏输入 |
| `minekin-runtime` | Soul/Memory 单写者、PlayerMind、目标、工具、World Capsule | Minecraft 按键、未经 Bridge 过滤的世界真值 |
| `minekin-launcher` | bundle/cache、身份 profile、子进程、IPC端点/一次性凭据 | 人格、关系与目标 |
| Minecraft JVM + Bridge | 当前会话观察、输入、反射、动作结果 | 长期人格、网页工具、跨世界数据库 |
| `media-worker` | 只读帧源、编码、短期观看发布凭据 | 控制 IPC、Memory、在线认证令牌 |

启动顺序：身份/数据库检查 → Server Profile/bundle → 新 session generation 与 IPC 目录 → Runtime/Launcher → Minecraft JVM → Bridge 握手 → 允许入服。关闭先禁止新 intent、撤销 lease、松键，再停媒体、断游戏、提交会话，最后关数据库。

## 端点与握手

Linux 候选为运行时私有目录中的 `control.sock` 和 `event.sock`；Windows 使用两个随机 loopback 端口。端点不监听 `0.0.0.0`，不经反向代理公开。

Launcher 每次生成新的 `session_id/session_generation`、256-bit 随机会话密钥，以及预期 `kin_id`、`server_profile_id`、`world_context_id`、bundle/Bridge hash。密钥经权限受限的一次性文件或句柄交付，不进入 argv、Dashboard、日志或模型上下文。

握手交换 `protocol_major/minor`、构建 hash、Minecraft/Fabric 版本、capability manifest、nonce 与密钥证明。major 不兼容、bundle/capability 不符、重放或身份字段不一致时，Bridge 保持无输入并拒绝激活。

## Protobuf envelope

每帧为固定宽度网络字节序长度前缀 + Protobuf `Envelope`，设置最大帧长。字段至少包括：

- protocol major/minor、session id/generation；
- channel、message type、sequence、reply_to；
- monotonic time、可选 game tick；
- intent generation、lease id、deadline；
- payload、可选 trace id。

[Protobuf 官方指南](https://protobuf.dev/programming-guides/proto3/#updating)要求字段号不能改号/复用，删除字段应 reserved。Minekin 只合入经过兼容测试的 wire-safe 增量；协议文件和生成代码随 bundle 固定 hash。

## 双通道与背压

**control**：握手、heartbeat、intent、cancel、lease、pause/resume、safe-stop、结果确认。队列有界，不能被观察或日志占满。持有型输入必须有短 lease；lease 到期、generation 改变、GUI/死亡/断线或 control 丢失时，Bridge 本地松开全部输入。

**event**：过滤观察、动作结果、连接/GUI状态、指标与诊断。

- 必达：连接变化、死亡、GUI generation、最终动作结果、反射抢占、安全故障；
- 可合并：HUD/位置/视角的最新状态；
- 可丢：重复调试采样。

高水位时先合并/丢弃低级事件并计数，不能阻塞客户端 tick。sequence 有缺口时请求新快照，不脑补成功。视频完全旁路。

## 心跳、动作与失败

P0 可从 500 ms heartbeat、连续 3 次丢失进入失联候选开始测试；这不是最终保证。危险动作 lease 必须短于失联窗口。Bridge 的反射不依赖心跳，但失联后只允许保命、松键和安全退出，不能继续高层计划。

离散动作带唯一 `action_id`，结果区分 `accepted/started/succeeded/failed/cancelled/unknown_after_disconnect`。Runtime 不自动重放攻击、丢物、箱子转移、合成或放置；先观察结果。旧 generation 的迟到模型输出、事件和确认一律拒绝。

## 部署档

### P0 Linux

Ubuntu 24.04/同类 systemd 主机、Java 21、Python 3.12、Xvfb/正常 OpenGL。systemd/cgroup 候选限制 `MemoryMax/CPUQuota/TasksMax`，并逐项测试 `NoNewPrivileges/PrivateTmp/ProtectSystem`；不能套最高限制后假装 Java natives、显示和媒体仍可用。

先宿主机分进程跑通，以免容器、GPU透传、虚拟显示、动作与 Agent 故障互相掩盖。闭环稳定后再生成 rootless OCI/Compose profile；容器仍须保持相同 IPC、uid/volume 与 secrets 规则。

### Windows 开发档

同一协议走随机 loopback TCP。Windows 服务化、Job Object、隐藏窗口和媒体采集单独原型，不能因 Linux 可用就宣称跨平台完成。

## 必须验证

1. 正确/错误协议、bundle hash、capability、token 与 generation 握手；
2. event 洪水、慢 Runtime、半帧、超长帧、重复 action id；
3. 五类进程分别强杀，验证松键、故障区分和无危险重放；
4. 切服时旧 lease、实体、GUI 与 plan execution 全失效；
5. Dashboard 无法取得 Bridge 凭据或发输入；
6. Linux UDS/Windows loopback 的吞吐、CPU、p50/p95/p99 和队列水位；
7. systemd 限制、磁盘满、PID耗尽、崩溃循环与日志轮转；
8. Protobuf 新旧 minor 互通、reserved 字段及 major 阻断。

原型通过后才冻结 heartbeat、lease、frame、队列和资源配额。当前不声明零延迟、零丢失或绝对隔离。